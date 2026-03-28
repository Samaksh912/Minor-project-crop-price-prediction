import 'dart:ui';

// ─────────────────────────────────────────────
// Crop (displayed in the home grid)
// ─────────────────────────────────────────────
class Crop {
  final String id;
  final String name;       // matches backend CSV name e.g. "maize"
  final String displayName; // pretty name e.g. "Maize"
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
// Model metrics
// ─────────────────────────────────────────────
class ModelMetrics {
  final double mae;
  final double rmse;
  final double mapePct;

  const ModelMetrics({
    required this.mae,
    required this.rmse,
    required this.mapePct,
  });

  /// Parse from backend format: { "mae": ..., "rmse": ..., "mape_pct": ... }
  factory ModelMetrics.fromBackendJson(Map<String, dynamic> json) =>
      ModelMetrics(
        mae: (json['mae'] as num).toDouble(),
        rmse: (json['rmse'] as num).toDouble(),
        mapePct: (json['mape_pct'] as num).toDouble(),
      );

  /// Synthetic metrics for Gemini / dummy data
  factory ModelMetrics.synthetic({
    double mae = 85.0,
    double rmse = 120.0,
    double mapePct = 6.5,
  }) =>
      ModelMetrics(mae: mae, rmse: rmse, mapePct: mapePct);
}

// ─────────────────────────────────────────────
// Price summary (derived / provided)
// ─────────────────────────────────────────────
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

  /// Build summary from a list of prediction points (90 days → 3 months)
  factory PriceSummary.fromPoints(List<PredictionPoint> points) {
    if (points.isEmpty) {
      return const PriceSummary(minPrice: 0, maxPrice: 0, avgPrice: 0);
    }
    final prices = points.map((p) => p.price).toList();
    final minP = prices.reduce((a, b) => a < b ? a : b);
    final maxP = prices.reduce((a, b) => a > b ? a : b);
    final avgP = prices.reduce((a, b) => a + b) / prices.length;

    double? m1, m2, m3;
    if (points.length >= 30) {
      final s1 = points.sublist(0, 30).map((p) => p.price);
      m1 = s1.reduce((a, b) => a + b) / 30;
    }
    if (points.length >= 60) {
      final s2 = points.sublist(30, 60).map((p) => p.price);
      m2 = s2.reduce((a, b) => a + b) / 30;
    }
    if (points.length >= 90) {
      final s3 = points.sublist(60, 90).map((p) => p.price);
      m3 = s3.reduce((a, b) => a + b) / 30;
    }

    return PriceSummary(
      minPrice: minP,
      maxPrice: maxP,
      avgPrice: avgP,
      month1Avg: m1,
      month2Avg: m2,
      month3Avg: m3,
    );
  }
}

// ─────────────────────────────────────────────
// Data source tag (hidden from users)
// ─────────────────────────────────────────────
enum PredictionSource { backend, gemini, dummy }

// ─────────────────────────────────────────────
// Full prediction response – unified model
// ─────────────────────────────────────────────
class PredictionResponse {
  final String crop;
  final String unit;
  final String bestModelName;
  final int forecastHorizonDays;
  final DateTime generatedAt;
  final DateTime lastObservedDate;
  final ModelMetrics metrics;
  final List<PredictionPoint> predictions;
  final PriceSummary summary;
  final PredictionSource source; // internal – never shown to user

  const PredictionResponse({
    required this.crop,
    required this.unit,
    required this.bestModelName,
    required this.forecastHorizonDays,
    required this.generatedAt,
    required this.lastObservedDate,
    required this.metrics,
    required this.predictions,
    required this.summary,
    this.source = PredictionSource.backend,
  });

  // ── Factory: parse actual backend JSON ─────────────────────────────────────
  // Expected shape:
  // {
  //   "status": "ok",
  //   "crop": "maize",
  //   "best_model_name": "Hybrid_ARIMAX_LSTM",
  //   "metrics": { "mae": 55.3, "rmse": 82.1, "mape_pct": 4.7 },
  //   "forecast_dates": ["2025-04-01", ...],   // 90 items
  //   "forecast": [1120.5, ...]                // 90 items
  // }
  factory PredictionResponse.fromBackendJson(Map<String, dynamic> json) {
    final rawDates = List<String>.from(json['forecast_dates'] as List);
    final rawForecast = List<dynamic>.from(json['forecast'] as List);

    final points = List.generate(
      rawDates.length,
      (i) => PredictionPoint(
        date: DateTime.parse(rawDates[i]),
        price: (rawForecast[i] as num).toDouble(),
      ),
    );

    final metricsRaw = json['metrics'] as Map<String, dynamic>?;
    final metrics = metricsRaw != null
        ? ModelMetrics.fromBackendJson(metricsRaw)
        : ModelMetrics.synthetic();

    // Use first forecast date as lastObservedDate approximation
    final lastObserved = points.isNotEmpty
        ? points.first.date.subtract(const Duration(days: 7))
        : DateTime.now();

    return PredictionResponse(
      crop: json['crop'] as String? ?? 'maize',
      unit: 'Rs/Quintal',
      bestModelName: json['best_model_name'] as String? ?? 'AI Model',
      forecastHorizonDays: points.length,
      generatedAt: DateTime.now(),
      lastObservedDate: lastObserved,
      metrics: metrics,
      predictions: points,
      summary: PriceSummary.fromPoints(points),
      source: PredictionSource.backend,
    );
  }

  // ── Factory: build from a flat list of prices (Gemini / dummy) ─────────────
  factory PredictionResponse.fromPriceList({
    required String cropName,
    required List<double> prices,
    ModelMetrics? metrics,
    PredictionSource source = PredictionSource.gemini,
  }) {
    final startDate = DateTime.now().add(const Duration(days: 1));
    final points = List.generate(
      prices.length,
      (i) => PredictionPoint(
        date: startDate.add(Duration(days: i)),
        price: prices[i],
      ),
    );

    return PredictionResponse(
      crop: cropName,
      unit: 'Rs/Quintal',
      bestModelName: 'AI Forecast',
      forecastHorizonDays: prices.length,
      generatedAt: DateTime.now(),
      lastObservedDate: DateTime.now(),
      metrics: metrics ?? ModelMetrics.synthetic(),
      predictions: points,
      summary: PriceSummary.fromPoints(points),
      source: source,
    );
  }

  // ── Convenience accessors for UI ───────────────────────────────────────────

  List<PredictionPoint> inRange(DateTime start, DateTime end) {
    return predictions
        .where((p) => !p.date.isBefore(start) && !p.date.isAfter(end))
        .toList();
  }

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
