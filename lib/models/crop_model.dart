import 'dart:ui';

// ─────────────────────────────────────────────
// Crop (displayed in the home grid)
// ─────────────────────────────────────────────
class Crop {
  final String id;
  final String name;       // matches backend CSV name e.g. "apple"
  final String displayName; // pretty name e.g. "Apple"
  final String category;
  final String emoji;

  const Crop({
    required this.id,
    required this.name,
    required this.displayName,
    required this.category,
    required this.emoji,
  });

  // Legacy compat — widgets that used imageUrl get emoji instead
  String get imageUrl => emoji;
}

// ─────────────────────────────────────────────
// Single daily prediction point
// ─────────────────────────────────────────────
class PredictionPoint {
  final DateTime date;
  final double price;

  const PredictionPoint({required this.date, required this.price});
}

// ─────────────────────────────────────────────
// Full prediction response from backend
// ─────────────────────────────────────────────
class PredictionResponse {
  final String crop;
  final String unit;
  final int forecastHorizonDays;
  final DateTime generatedAt;
  final DateTime lastObservedDate;
  final ModelMetrics metrics;
  final List<PredictionPoint> predictions;
  final PriceSummary summary;

  const PredictionResponse({
    required this.crop,
    required this.unit,
    required this.forecastHorizonDays,
    required this.generatedAt,
    required this.lastObservedDate,
    required this.metrics,
    required this.predictions,
    required this.summary,
  });

  factory PredictionResponse.fromJson(Map<String, dynamic> json) {
    final rawPredictions = json['predictions'] as List<dynamic>;
    return PredictionResponse(
      crop: json['crop'] as String,
      unit: json['unit'] as String,
      forecastHorizonDays: json['forecast_horizon_days'] as int,
      generatedAt: DateTime.parse(json['generated_at'] as String),
      lastObservedDate: DateTime.parse(json['last_observed_date'] as String),
      metrics: ModelMetrics.fromJson(json['model_metrics'] as Map<String, dynamic>),
      predictions: rawPredictions
          .map((e) => PredictionPoint(
                date: DateTime.parse(e['date'] as String),
                price: (e['predicted_modal_price'] as num).toDouble(),
              ))
          .toList(),
      summary: PriceSummary.fromJson(json['summary'] as Map<String, dynamic>),
    );
  }

  // ── Convenience accessors for the UI ──────────────────────────────────────

  /// Filter predictions array to only the given date window
  List<PredictionPoint> inRange(DateTime start, DateTime end) {
    return predictions
        .where((p) =>
            !p.date.isBefore(start) && !p.date.isAfter(end))
        .toList();
  }

  /// Derive accuracy percentage from MAPE (100 - mape, clamped 0–100)
  double get accuracyPct => (100 - metrics.mapePct).clamp(0, 100);

  String get accuracyLabel {
    if (accuracyPct >= 90) return 'High Accuracy';
    if (accuracyPct >= 70) return 'Moderate Accuracy';
    return 'Low Accuracy';
  }

  Color get accuracyColor {
    if (accuracyPct >= 90) return const Color(0xFF2E7D32);
    if (accuracyPct >= 70) return const Color(0xFFF57C00);
    return const Color(0xFFD32F2F);
  }
}

class ModelMetrics {
  final double mae;
  final double rmse;
  final double mapePct;

  const ModelMetrics({
    required this.mae,
    required this.rmse,
    required this.mapePct,
  });

  factory ModelMetrics.fromJson(Map<String, dynamic> json) => ModelMetrics(
        mae: (json['mae'] as num).toDouble(),
        rmse: (json['rmse'] as num).toDouble(),
        mapePct: (json['mape_pct'] as num).toDouble(),
      );
}

class PriceSummary {
  final double minPrice;
  final double maxPrice;
  final double avgPrice;
  final double? month1Avg;
  final double? month2Avg;
  final double? month3Avg;

  const PriceSummary({
    required this.minPrice,
    required this.maxPrice,
    required this.avgPrice,
    this.month1Avg,
    this.month2Avg,
    this.month3Avg,
  });

  factory PriceSummary.fromJson(Map<String, dynamic> json) => PriceSummary(
        minPrice: (json['min_price'] as num).toDouble(),
        maxPrice: (json['max_price'] as num).toDouble(),
        avgPrice: (json['avg_price'] as num).toDouble(),
        month1Avg: json['month_1_avg'] != null
            ? (json['month_1_avg'] as num).toDouble()
            : null,
        month2Avg: json['month_2_avg'] != null
            ? (json['month_2_avg'] as num).toDouble()
            : null,
        month3Avg: json['month_3_avg'] != null
            ? (json['month_3_avg'] as num).toDouble()
            : null,
      );
}

// ─────────────────────────────────────────────
// Legacy alias kept so existing widgets compile
// ─────────────────────────────────────────────
class PredictionResult {
  final String cropName;
  final DateTime date;
  final double predictedPrice;
  final double accuracy;
  final String timeRange;

  const PredictionResult({
    required this.cropName,
    required this.date,
    required this.predictedPrice,
    required this.accuracy,
    required this.timeRange,
  });

  String get accuracyLabel {
    if (accuracy >= 90) return 'High Accuracy';
    if (accuracy >= 60) return 'Moderate Accuracy';
    return 'Low Accuracy';
  }

  Color get accuracyColor {
    if (accuracy >= 90) return const Color(0xFF2E7D32);
    if (accuracy >= 60) return const Color(0xFFF57C00);
    return const Color(0xFFD32F2F);
  }
}
