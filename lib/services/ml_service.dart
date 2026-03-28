import 'dart:convert';
import 'dart:math' as math;
import 'package:http/http.dart' as http;
import '../models/crop_model.dart';

// ─────────────────────────────────────────────────────────────────────────────
// Configuration
// ─────────────────────────────────────────────────────────────────────────────

/// Backend base URL — change to your machine's LAN IP when on a real device
/// e.g. 'http://192.168.1.16:5000'
const String _kBackendUrl = 'http://192.168.1.16:5000';

/// The only crop currently supported by the backend
const String _kBackendCrop = 'maize';

/// Gemini REST endpoint
/// gemini-3.1-flash-lite-preview: latest Flash-Lite, free tier, lowest cost & latency
const String _kGeminiModel = 'gemini-3.1-flash-lite-preview';
const String _kGeminiBaseUrl =
    'https://generativelanguage.googleapis.com/v1beta/models';

/// ⚠️  Replace with your actual Gemini API key or load from env / secure store
const String _kGeminiApiKey = 'AIzaSyB4PMYKxQIEYK2eapgTauAbI4WfYX_HEes';

// ─────────────────────────────────────────────────────────────────────────────
// MLService — unified entry-point for the provider
// ─────────────────────────────────────────────────────────────────────────────
class MLService {
  // ── Backend helpers ────────────────────────────────────────────────────────

  Future<List<String>> fetchAvailableCrops() async {
    final uri = Uri.parse('$_kBackendUrl/api/crops');
    final response = await http.get(uri).timeout(const Duration(seconds: 10));
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      return List<String>.from(data['crops'] as List);
    }
    throw Exception('Failed to load crop list: ${response.statusCode}');
  }

  Future<bool> isServerReachable() async {
    try {
      final response = await http
          .get(Uri.parse('$_kBackendUrl/api/health'))
          .timeout(const Duration(seconds: 5));
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  // ── Main fetch — routes based on crop name ─────────────────────────────────
  //
  // maize  → backend API → PredictionResponse.fromBackendJson
  // others → Gemini API  → PredictionResponse.fromPriceList (gemini source)
  //          on any failure → fallback dummy data
  // ──────────────────────────────────────────────────────────────────────────
  Future<PredictionResponse> fetchPredictions(String cropName) async {
    if (cropName.toLowerCase() == _kBackendCrop) {
      return _fetchFromBackend(cropName);
    } else {
      return _fetchFromGeminiOrFallback(cropName);
    }
  }

  // ── Backend call (maize) ───────────────────────────────────────────────────
  Future<PredictionResponse> _fetchFromBackend(String cropName) async {
    final uri = Uri.parse('$_kBackendUrl/api/predict');
    final response = await http
        .post(
          uri,
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'crop': cropName.toLowerCase()}),
        )
        .timeout(const Duration(minutes: 10));

    if (response.statusCode == 200) {
      return PredictionResponse.fromBackendJson(
        jsonDecode(response.body) as Map<String, dynamic>,
      );
    }

    final errorBody = jsonDecode(response.body) as Map<String, dynamic>;
    throw Exception(errorBody['message'] ?? 'Prediction failed');
  }

  // ── Gemini call (other crops) ──────────────────────────────────────────────
  Future<PredictionResponse> _fetchFromGeminiOrFallback(String cropName) async {
    try {
      return await _fetchFromGemini(cropName);
    } catch (_) {
      // Any failure → silent fallback to dummy
      return _buildDummyResponse(cropName);
    }
  }

  Future<PredictionResponse> _fetchFromGemini(String cropName) async {
    final url = Uri.parse(
      '$_kGeminiBaseUrl/$_kGeminiModel:generateContent?key=$_kGeminiApiKey',
    );

    // Compact prompt — minimises input tokens while preserving output structure
    final prompt = 'Return ONLY valid JSON, no markdown. '
        '90-day daily price forecast for "$cropName" in Tamil Nadu, India (Rs/Quintal). '
        'Schema: {"prices":[<90 floats>],"mae":<float>,"rmse":<float>,"mape_pct":<float 2-15>}';

    final body = jsonEncode({
      'contents': [
        {
          'parts': [
            {'text': prompt}
          ]
        }
      ],
      'generationConfig': {
        // Generative tokens for 90 floats + fields takes ~500-800 tokens. 1500 is safe.
        'maxOutputTokens': 1500,
      },
    });

    final response = await http
        .post(url, headers: {'Content-Type': 'application/json'}, body: body)
        .timeout(const Duration(seconds: 30));

    if (response.statusCode != 200) {
      throw Exception('Gemini returned ${response.statusCode}');
    }

    final json = jsonDecode(response.body) as Map<String, dynamic>;

    // Extract text from Gemini response
    final candidates = json['candidates'] as List<dynamic>;
    final text = (candidates.first['content']['parts'] as List<dynamic>)
        .first['text'] as String;

    // Strip possible markdown fences
    final cleaned = text.replaceAll('```json', '').replaceAll('```', '').trim();

    final parsed = jsonDecode(cleaned) as Map<String, dynamic>;
    final prices = (parsed['prices'] as List<dynamic>)
        .map((e) => (e as num).toDouble())
        .toList();

    if (prices.length < 60) {
      throw Exception('Gemini returned insufficient data');
    }

    final metrics = ModelMetrics.synthetic(
      mae: (parsed['mae'] as num?)?.toDouble() ?? 85.0,
      rmse: (parsed['rmse'] as num?)?.toDouble() ?? 120.0,
      mapePct: (parsed['mape_pct'] as num?)?.toDouble() ?? 6.5,
    );

    return PredictionResponse.fromPriceList(
      cropName: cropName,
      prices: prices,
      metrics: metrics,
      source: PredictionSource.gemini,
    );
  }

  // ── Dummy fallback data ────────────────────────────────────────────────────
  PredictionResponse _buildDummyResponse(String cropName) {
    // Base prices per crop (Rs/Quintal) — realistic Indian market ranges
    const basePrices = <String, double>{
      'apple': 4500,
      'bananagreen': 1800,
      'mango': 2800,
      'lemon': 3200,
      'beans': 2200,
      'beetroot': 1500,
      'ladies_finger': 2600,
    };

    final key = cropName.toLowerCase();
    final basePrice = basePrices[key] ?? 2000.0;

    // Generate a 90-day pseudo-random but deterministic series
    final rng = math.Random(key.hashCode);
    final prices = List.generate(90, (i) {
      // Gentle sine wave + small noise
      final trend = basePrice + (basePrice * 0.05 * math.sin(i * math.pi / 45));
      final noise = (rng.nextDouble() - 0.5) * basePrice * 0.03;
      return (trend + noise).clamp(basePrice * 0.7, basePrice * 1.4);
    });

    return PredictionResponse.fromPriceList(
      cropName: cropName,
      prices: prices,
      metrics: ModelMetrics.synthetic(
        mae: basePrice * 0.04,
        rmse: basePrice * 0.06,
        mapePct: 6.0,
      ),
      source: PredictionSource.dummy,
    );
  }
}
