// SPDX-FileCopyrightText: 2019 - 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

#include <functional>
#include <limits>
#include <numeric>
#include <opencv2/core.hpp>
#include <omp.h>

#include "rv/Utils.hpp"
#include "rv/tracking/ObjectMatching.hpp"
#include "rv/apollo/multi_hm_bipartite_graph_matcher.hpp"
#include "rv/apollo/secure_matrix.hpp"
#include "rv/tracking/Classification.hpp"
#include "rv/tracking/OrientationAttributes.hpp"

namespace rv {
namespace tracking {

constexpr double kDefaultClassBoundValue = 1000.;

namespace {

/// True when the association gate should use S = H P H^T + R_detection for this pair.
bool usesMeasurementNoise(const TrackedObject &measurement, const TrackedObject &track)
{
  return measurement.hasMeasurementNoise()
         && track.predictedStateMeasurementCov.rows == TrackedObject::MeasurementSize
         && track.predictedStateMeasurementCov.cols == TrackedObject::MeasurementSize;
}

cv::Matx33d positionBlock(const cv::Mat &cov)
{
  return cv::Matx33d(cov.at<double>(MeasurementIndex::X, MeasurementIndex::X),
                     cov.at<double>(MeasurementIndex::X, MeasurementIndex::Y),
                     cov.at<double>(MeasurementIndex::X, MeasurementIndex::Z),
                     cov.at<double>(MeasurementIndex::Y, MeasurementIndex::X),
                     cov.at<double>(MeasurementIndex::Y, MeasurementIndex::Y),
                     cov.at<double>(MeasurementIndex::Y, MeasurementIndex::Z),
                     cov.at<double>(MeasurementIndex::Z, MeasurementIndex::X),
                     cov.at<double>(MeasurementIndex::Z, MeasurementIndex::Y),
                     cov.at<double>(MeasurementIndex::Z, MeasurementIndex::Z));
}

} // namespace

double calculateMulticlassScaledDistance(const TrackedObject &measurement, const TrackedObject &track)
{
  auto conflict = rv::tracking::classification::distance(measurement.classification, track.classification);

  double distance = std::sqrt(pow(measurement.x - track.x, 2) + pow(measurement.y - track.y, 2)
                              + pow(measurement.z - track.z, 2));

  return distance * (1.0 + conflict);
}

double calculateEuclideanDistance(const TrackedObject &measurement, const TrackedObject &track)
{
  return std::sqrt(pow(measurement.x - track.x, 2) + pow(measurement.y - track.y, 2)
                   + pow(measurement.z - track.z, 2));
}

/// Birth clustering: XY when either detection is planar (no measured Z); full XYZ when both are.
double calculateEuclideanBirthDistance(const TrackedObject &measurement, const TrackedObject &track)
{
  const double dx = measurement.x - track.x;
  const double dy = measurement.y - track.y;
  if (!(measurement.zMeasured && track.zMeasured))
  {
    return std::hypot(dx, dy);
  }
  const double dz = measurement.z - track.z;
  return std::sqrt(dx * dx + dy * dy + dz * dz);
}

double calculateMahalanobisDistance(const TrackedObject &measurement, const TrackedObject &track)
{
  cv::Mat innovation = measurement.measurementVector() - (track.predictedMeasurementMean);

  // Use yaw in the gate only when both sides have orientation. Camera detections
  // and tracks that have never seen an orienting sensor leave yaw out.
  if (!(orientation::hasOrientation(measurement) && orientation::orientationObserved(track)))
  {
    innovation.at<double>(MeasurementIndex::YAW, 0) = 0.;
  }

  cv::Mat covarianceInv = track.predictedMeasurementCovInv;
  if (usesMeasurementNoise(measurement, track))
  {
    covarianceInv = (track.predictedStateMeasurementCov + measurement.measurementNoiseCov).inv(cv::DECOMP_SVD);
  }

  cv::Mat mahalanobisDistance = innovation.t() * covarianceInv * innovation;

  return 0.5 * std::sqrt(mahalanobisDistance.at<double>(0, 0));
}

/// Squared position Mahalanobis distance d^2 = v^T S^-1 v (v = detection - predicted xyz).
/// S is the track's predicted S, or H P H^T + R_detection when the detection carries R.
double calculatePositionMahalanobisSquaredDistance(const TrackedObject &measurement, const TrackedObject &track)
{
  const cv::Vec3d innovation(
    measurement.x - track.predictedMeasurementMean.at<double>(MeasurementIndex::X, 0),
    measurement.y - track.predictedMeasurementMean.at<double>(MeasurementIndex::Y, 0),
    measurement.z - track.predictedMeasurementMean.at<double>(MeasurementIndex::Z, 0));

  cv::Matx33d S = usesMeasurementNoise(measurement, track)
    ? positionBlock(track.predictedStateMeasurementCov) + positionBlock(measurement.measurementNoiseCov)
    : positionBlock(track.predictedMeasurementCov);

  bool invertible = false;
  const cv::Matx33d Sinv = S.inv(cv::DECOMP_LU, &invertible);
  if (!invertible)
  {
    return kDefaultClassBoundValue;
  }
  return innovation.dot(Sinv * innovation);
}

namespace {

/// Per-track constants for PositionMahalanobis cost fill (S^{-1} is fixed for the frame).
struct PositionMahalanobisTrackCache
{
  double pred_x = 0.0;
  double pred_y = 0.0;
  double pred_z = 0.0;
  double inv00 = 0.0;
  double inv01 = 0.0;
  double inv02 = 0.0;
  double inv11 = 0.0;
  double inv12 = 0.0;
  double inv22 = 0.0;
  bool valid = false;
};

PositionMahalanobisTrackCache buildPositionMahalanobisTrackCache(const TrackedObject &track)
{
  PositionMahalanobisTrackCache cache;
  cache.pred_x = track.predictedMeasurementMean.at<double>(MeasurementIndex::X, 0);
  cache.pred_y = track.predictedMeasurementMean.at<double>(MeasurementIndex::Y, 0);
  cache.pred_z = track.predictedMeasurementMean.at<double>(MeasurementIndex::Z, 0);

  cv::Mat S = (cv::Mat_<double>(3, 3) <<
    track.predictedMeasurementCov.at<double>(MeasurementIndex::X, MeasurementIndex::X),
    track.predictedMeasurementCov.at<double>(MeasurementIndex::X, MeasurementIndex::Y),
    track.predictedMeasurementCov.at<double>(MeasurementIndex::X, MeasurementIndex::Z),
    track.predictedMeasurementCov.at<double>(MeasurementIndex::Y, MeasurementIndex::X),
    track.predictedMeasurementCov.at<double>(MeasurementIndex::Y, MeasurementIndex::Y),
    track.predictedMeasurementCov.at<double>(MeasurementIndex::Y, MeasurementIndex::Z),
    track.predictedMeasurementCov.at<double>(MeasurementIndex::Z, MeasurementIndex::X),
    track.predictedMeasurementCov.at<double>(MeasurementIndex::Z, MeasurementIndex::Y),
    track.predictedMeasurementCov.at<double>(MeasurementIndex::Z, MeasurementIndex::Z));

  cv::Mat Sinv;
  if (cv::invert(S, Sinv, cv::DECOMP_LU) == 0)
  {
    return cache;
  }
  cache.inv00 = Sinv.at<double>(0, 0);
  cache.inv01 = Sinv.at<double>(0, 1);
  cache.inv02 = Sinv.at<double>(0, 2);
  cache.inv11 = Sinv.at<double>(1, 1);
  cache.inv12 = Sinv.at<double>(1, 2);
  cache.inv22 = Sinv.at<double>(2, 2);
  cache.valid = true;
  return cache;
}

double positionMahalanobisCostFromCache(double measurement_x, double measurement_y, double measurement_z,
                                        const PositionMahalanobisTrackCache &cache, double max_radius_m)
{
  const double dx = measurement_x - cache.pred_x;
  const double dy = measurement_y - cache.pred_y;
  const double dz = measurement_z - cache.pred_z;
  if (std::sqrt(dx * dx + dy * dy + dz * dz) > max_radius_m)
  {
    return kDefaultClassBoundValue;
  }
  if (!cache.valid)
  {
    return kDefaultClassBoundValue;
  }
  return dx * (cache.inv00 * dx + cache.inv01 * dy + cache.inv02 * dz)
       + dy * (cache.inv01 * dx + cache.inv11 * dy + cache.inv12 * dz)
       + dz * (cache.inv02 * dx + cache.inv12 * dy + cache.inv22 * dz);
}

} // namespace

double calculateCompundDistance(const TrackedObject &measurement, const TrackedObject &track)
{
  double euclideanDist = calculateMulticlassScaledDistance(measurement, track);
  double mahalanobisDist = calculateMahalanobisDistance(measurement, track);

  return 0.5 * euclideanDist + 0.5 * mahalanobisDist;
}

void match(const std::vector<TrackedObject> &tracks,
                          const std::vector<TrackedObject> &measurements,
                          std::vector<std::pair<size_t, size_t>> &assignments,
                          std::vector<size_t> &unassignedTracks,
                          std::vector<size_t> &unassignedMeasurements,
                          const DistanceType &distanceType, double threshold, double max_radius_m)
{
  apollo::perception::lidar::MultiHmBipartiteGraphMatcher matcher;

  matcher.cost_matrix()->Reserve(tracks.size(), measurements.size());

  assignments.clear();
  unassignedTracks.clear();
  unassignedMeasurements.clear();
  if (measurements.empty() || tracks.empty())
  {
    unassignedMeasurements.resize(measurements.size());
    unassignedTracks.resize(tracks.size());

    std::iota(unassignedMeasurements.begin(), unassignedMeasurements.end(), 0);
    std::iota(unassignedTracks.begin(), unassignedTracks.end(), 0);
    return;
  }

  apollo::perception::lidar::BipartiteGraphMatcherOptions matcherOptions;
  matcherOptions.cost_thresh = threshold;
  matcherOptions.bound_value = kDefaultClassBoundValue;

  apollo::perception::common::SecureMat<double> *costMatrix = matcher.cost_matrix();
  costMatrix->Resize(tracks.size(), measurements.size());

  if (distanceType == DistanceType::PositionMahalanobis)
  {
    // Invert the 3x3 position covariance once per track, not once per (track, detection).
    std::vector<PositionMahalanobisTrackCache> track_caches(tracks.size());
    for (size_t i = 0; i < tracks.size(); ++i)
    {
      track_caches[i] = buildPositionMahalanobisTrackCache(tracks[i]);
    }

    #pragma omp parallel for collapse(2)
    for (size_t i = 0; i < tracks.size(); ++i)
    {
      for (size_t j = 0; j < measurements.size(); ++j)
      {
        if (usesMeasurementNoise(measurements[j], tracks[i]))
        {
          // Per-pair S = H P H^T + R_j: cannot use the per-track cached S^-1.
          const auto &cache = track_caches[i];
          const double dx = measurements[j].x - cache.pred_x;
          const double dy = measurements[j].y - cache.pred_y;
          const double dz = measurements[j].z - cache.pred_z;
          (*costMatrix)(i, j) = (std::sqrt(dx * dx + dy * dy + dz * dz) > max_radius_m)
            ? kDefaultClassBoundValue
            : calculatePositionMahalanobisSquaredDistance(measurements[j], tracks[i]);
          continue;
        }
        (*costMatrix)(i, j) = positionMahalanobisCostFromCache(
          measurements[j].x, measurements[j].y, measurements[j].z, track_caches[i], max_radius_m);
      }
    }
  }
  else
  {
    std::function<double(const TrackedObject &, const TrackedObject &)> distanceFunction;
    switch (distanceType)
    {
      case DistanceType::MCEMahalanobis:
        distanceFunction = std::bind(&calculateCompundDistance, std::placeholders::_1, std::placeholders::_2);
        break;
      case DistanceType::Mahalanobis:
        distanceFunction = std::bind(&calculateMahalanobisDistance, std::placeholders::_1, std::placeholders::_2);
        break;
      case DistanceType::MultiClassEuclidean:
        distanceFunction = std::bind(&calculateMulticlassScaledDistance, std::placeholders::_1, std::placeholders::_2);
        break;
      case DistanceType::EuclideanBirth:
        distanceFunction = [max_radius_m](const TrackedObject &measurement, const TrackedObject &track) {
          const double distance = calculateEuclideanBirthDistance(measurement, track);
          if (distance > max_radius_m)
          {
            return kDefaultClassBoundValue;
          }
          return distance;
        };
        break;
      case DistanceType::Euclidean:
      default:
        distanceFunction = [max_radius_m](const TrackedObject &measurement, const TrackedObject &track) {
          const double distance = calculateEuclideanDistance(measurement, track);
          if (distance > max_radius_m)
          {
            return kDefaultClassBoundValue;
          }
          return distance;
        };
        break;
    }

    #pragma omp parallel for collapse(2)
    for (size_t i = 0; i < tracks.size(); ++i)
    {
      for (size_t j = 0; j < measurements.size(); ++j)
      {
        (*costMatrix)(i, j) = distanceFunction(measurements[j], tracks[i]);
      }
    }
  }

  matcher.Match(matcherOptions, &assignments, &unassignedTracks, &unassignedMeasurements);
}

} // namespace tracking
} // namespace rv
