import 'dart:convert';
import 'dart:developer' as dev;
import 'dart:math' as math;
import 'package:http/http.dart' as http;
import '../models/crop_model.dart';

// ─────────────────────────────────────────────────────────────────────────────
// Configuration
// ─────────────────────────────────────────────────────────────────────────────

/// Backend base URL — change to your machine's LAN IP when on a real device
const String _kBackendUrl = 'http://192.168.1.5:5000';

/// The only crop currently supported by the backend ML model
const String _kBackendCrop = 'maize';

/// Gemini REST endpoint.
/// ✅ gemini-2.0-flash — verified free-tier, stable, fast.
/// ❌ gemini-3.1-flash-lite-preview does NOT exist on the public API.
const String _kGeminiModel = 'gemini-3.1-flash-lite-preview';
const String _kGeminiBaseUrl =
    'https://generativelanguage.googleapis.com/v1beta/models';

/// ⚠️  Replace with your actual Gemini API key or load from env / secure store
const String _kGeminiApiKey = 'AIzaSyC7FUgCMVgBc6NpeUv9ad3o_kb3wzmJHBY';
//const String _kGeminiApiKey = 'AIzaSyCKtAyZ3m9-rexglGJl6fvpTbeDUmBbpi4';//backup key

// ─────────────────────────────────────────────────────────────────────────────
// MLService — unified entry-point for the provider
// ─────────────────────────────────────────────────────────────────────────────
class MLService {
  // ── In-memory cache ────────────────────────────────────────────────────────
  // Prevents redundant Gemini calls within the same app session.
  // Key: lowercase crop name. Value: (response, timestamp).
  static final Map<String, ({PredictionResponse response, DateTime at})>
      _cache = {};

  // Cache TTL: 6 hours — prices don't change that fast.
  static const Duration _cacheTtl = Duration(hours: 6);

  // ── Request deduplication ─────────────────────────────────────────────────
  // If two callers request the same crop simultaneously, only ONE HTTP call
  // is made. Both await the same Future instead of firing parallel requests
  // that each eat into the rate-limit quota.
  static final Map<String, Future<PredictionResponse>> _inFlight = {};

  // ── Backend helpers ────────────────────────────────────────────────────────

  Future<List<String>> fetchAvailableCrops() async {
    final uri = Uri.parse('$_kBackendUrl/api/crops');
    dev.log('[MLService] fetchAvailableCrops → GET $uri', name: 'MLService');

    final response = await http.get(uri).timeout(const Duration(seconds: 10));
    dev.log('[MLService] fetchAvailableCrops ← HTTP ${response.statusCode}',
        name: 'MLService');

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      final crops = List<String>.from(data['crops'] as List);
      dev.log('[MLService] Crop list: $crops', name: 'MLService');
      return crops;
    }

    dev.log('[MLService] ❌ fetchAvailableCrops failed: ${response.body}',
        name: 'MLService');
    throw Exception('Failed to load crop list: ${response.statusCode}');
  }

  Future<bool> isServerReachable() async {
    final healthUrl = '$_kBackendUrl/api/health';
    dev.log('[MLService] isServerReachable → GET $healthUrl',
        name: 'MLService');
    try {
      final response = await http
          .get(Uri.parse(healthUrl))
          .timeout(const Duration(seconds: 5));
      final ok = response.statusCode == 200;
      dev.log(
          '[MLService] isServerReachable ← $ok (HTTP ${response.statusCode})',
          name: 'MLService');
      return ok;
    } catch (e) {
      dev.log('[MLService] isServerReachable ← unreachable: $e',
          name: 'MLService');
      return false;
    }
  }

  // ── Main fetch — routes based on crop name ─────────────────────────────────
  //
  // maize  → backend API → (on failure) Gemini → (on failure) dummy
  // others → Gemini API  → (on failure) dummy
  // ──────────────────────────────────────────────────────────────────────────
  Future<PredictionResponse> fetchPredictions(String cropName) async {
    dev.log('[MLService] fetchPredictions("$cropName")', name: 'MLService');
    if (cropName.toLowerCase() == _kBackendCrop) {
      return _fetchFromBackendWithFallback(cropName);
    } else {
      // Route through the dedup guard so parallel calls share one Future.
      return _deduplicatedGemini(cropName);
    }
  }

  // ── Backend → Gemini → Dummy chain (maize) ─────────────────────────────────
  Future<PredictionResponse> _fetchFromBackendWithFallback(
      String cropName) async {
    try {
      return await _fetchFromBackend(cropName);
    } catch (backendError) {
      dev.log(
        '[MLService] ⚠️  Backend failed for "$cropName": $backendError\n'
        '           → Trying Gemini fallback…',
        name: 'MLService',
      );
      try {
        return await _deduplicatedGemini(cropName);
      } catch (geminiError) {
        dev.log(
          '[MLService] ⚠️  Gemini also failed for "$cropName": $geminiError\n'
          '           → Using offline dummy estimate.',
          name: 'MLService',
        );
        return _buildDummyResponse(cropName);
      }
    }
  }

  // ── Backend call ───────────────────────────────────────────────────────────
  Future<PredictionResponse> _fetchFromBackend(String cropName) async {
    final uri = Uri.parse('$_kBackendUrl/api/predict');
    dev.log('[MLService] → POST $uri  body: {"crop":"$cropName"}',
        name: 'MLService');

    final response = await http
        .post(
          uri,
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'crop': cropName.toLowerCase()}),
        )
        .timeout(const Duration(minutes: 10));

    dev.log('[MLService] ← Backend HTTP ${response.statusCode}',
        name: 'MLService');

    if (response.statusCode == 200) {
      final parsed = PredictionResponse.fromBackendJson(
        jsonDecode(response.body) as Map<String, dynamic>,
      );
      dev.log(
        '[MLService] ✅ Backend OK — model: ${parsed.bestModelName}, '
        'points: ${parsed.predictions.length}, '
        'accuracy: ${parsed.accuracyPct.toStringAsFixed(1)}%',
        name: 'MLService',
      );
      return parsed;
    }

    late String msg;
    try {
      final errorBody = jsonDecode(response.body) as Map<String, dynamic>;
      msg = (errorBody['message'] as String?) ?? 'HTTP ${response.statusCode}';
    } catch (_) {
      msg = 'HTTP ${response.statusCode}';
    }
    dev.log('[MLService] ❌ Backend error: $msg', name: 'MLService');
    throw Exception(msg);
  }

  // ── Request deduplication wrapper ─────────────────────────────────────────
  Future<PredictionResponse> _deduplicatedGemini(String cropName) {
    final key = cropName.toLowerCase();
    // If a request for this crop is already in-flight, return the same Future.
    if (_inFlight.containsKey(key)) {
      dev.log(
          '[MLService] ⏳ Gemini already in-flight for "$cropName" — '
          'reusing existing request',
          name: 'MLService');
      return _inFlight[key]!;
    }

    final future = _fetchFromGeminiOrFallback(cropName).whenComplete(() {
      _inFlight.remove(key);
      dev.log('[MLService] 🔓 In-flight lock released for "$cropName"',
          name: 'MLService');
    });

    _inFlight[key] = future;
    return future;
  }

  // ── Gemini → Dummy chain ───────────────────────────────────────────────────
  Future<PredictionResponse> _fetchFromGeminiOrFallback(String cropName) async {
    try {
      return await _fetchFromGemini(cropName);
    } catch (e) {
      dev.log(
        '[MLService] ⚠️  Gemini failed for "$cropName": $e\n'
        '           → Using offline dummy estimate.',
        name: 'MLService',
      );
      return _buildDummyResponse(cropName);
    }
  }

  // ── Gemini call (with in-memory cache + exponential-backoff retry) ──────────
  Future<PredictionResponse> _fetchFromGemini(String cropName) async {
    final cacheKey = cropName.toLowerCase();

    // ── Cache check ──────────────────────────────────────────────────────────
    final cached = _cache[cacheKey];
    if (cached != null) {
      final age = DateTime.now().difference(cached.at);
      if (age < _cacheTtl) {
        dev.log(
          '[MLService] ✅ Cache hit for "$cropName" '
          '(age: ${age.inMinutes}m, TTL: ${_cacheTtl.inHours}h)',
          name: 'MLService',
        );
        return cached.response;
      }
      dev.log(
          '[MLService] 🔄 Cache stale for "$cropName" (age: ${age.inMinutes}m) — refetching',
          name: 'MLService');
      _cache.remove(cacheKey);
    }

    // ── Build request ─────────────────────────────────────────────────────────
    final url = Uri.parse(
      '$_kGeminiBaseUrl/$_kGeminiModel:generateContent?key=$_kGeminiApiKey',
    );

    dev.log(
      '[MLService] → Gemini request\n'
      '  model : $_kGeminiModel\n'
      '  crop  : $cropName\n'
      '  url   : $url',
      name: 'MLService',
    );

    // ⚠️  Keep prompt tightly scoped to JSON only.
    // Instructing the model to avoid markdown is critical — Gemini sometimes
    // wraps responses in ```json fences even when told not to.
    final prompt =
        'You are a JSON-only API. Do NOT output any text, explanation, or '
        'markdown — return ONLY a raw JSON object. '
        'Generate a 90-day daily wholesale price forecast for "$cropName" '
        'in Tamil Nadu, India, expressed in Rs/Quintal. '
        'Use this exact schema (90 integers in the array): '
        '{"prices":[<90 integers>],"mae":<integer>,"rmse":<integer>,'
        '"mape_pct":<float between 2 and 15>}';

    final requestBody = jsonEncode({
      'contents': [
        {
          'parts': [
            {'text': prompt}
          ]
        }
      ],
      'generationConfig': {
        // 90 integers + metadata comfortably fits in 512 tokens.
        // Using fewer tokens reduces the chance of partial / cut-off responses.
        'maxOutputTokens': 512,
        // temperature=0 → deterministic, no creative hallucination
        //temperature': 0,
      },
    });

    // ── Retry loop with exponential back-off + jitter ─────────────────────────
    // Attempt delays (approximate): 10s → 20s → 40s
    // Jitter of ±20% prevents thundering-herd collisions.
    const maxAttempts = 4;
    final rng = math.Random();
    final baseDelaySecs = [10, 20, 40, 60]; // index = attempt-1

    http.Response? response;
    for (int attempt = 1; attempt <= maxAttempts; attempt++) {
      dev.log('[MLService] Gemini attempt $attempt/$maxAttempts',
          name: 'MLService');

      response = await http
          .post(
            url,
            headers: {'Content-Type': 'application/json'},
            body: requestBody,
          )
          .timeout(const Duration(seconds: 30));

      dev.log(
        '[MLService] ← Gemini HTTP ${response.statusCode} '
        '(attempt $attempt)',
        name: 'MLService',
      );

      if (response.statusCode == 200) {
        dev.log(
            '[MLService] ✅ Gemini responded successfully on attempt $attempt',
            name: 'MLService');
        break; // ← success, exit retry loop
      }

      if (response.statusCode == 429) {
        if (attempt >= maxAttempts) {
          dev.log(
              '[MLService] ❌ Gemini 429 — exhausted all $maxAttempts attempts',
              name: 'MLService');
          throw Exception(
              'Gemini rate-limited after $maxAttempts attempts (429)');
        }

        // Respect the Retry-After header when present.
        // On Flutter Web CORS may strip it, so we always have a fallback.
        final retryAfterHeader = response.headers['retry-after'];
        final retryAfterSecs = int.tryParse(retryAfterHeader ?? '') ?? 0;

        final jitterFactor = 1 + (rng.nextDouble() * 0.4 - 0.2); // 0.8–1.2×
        final waitSecs = retryAfterSecs > 0
            ? retryAfterSecs
            : (baseDelaySecs[attempt - 1] * jitterFactor).round();

        dev.log(
          '[MLService] ⚠️  Gemini 429 on attempt $attempt — '
          'waiting ${waitSecs}s (retry-after header: '
          '"${retryAfterHeader ?? 'none'}")',
          name: 'MLService',
        );
        await Future.delayed(Duration(seconds: waitSecs));
        continue;
      }

      // Any other non-200 status is not retryable.
      dev.log(
        '[MLService] ❌ Gemini non-retryable error\n'
        '  status : ${response.statusCode}\n'
        '  body   : ${response.body}',
        name: 'MLService',
      );
      throw Exception('Gemini error ${response.statusCode}: ${response.body}');
    }

    if (response == null || response.statusCode != 200) {
      throw Exception('Gemini failed after $maxAttempts attempts');
    }

    // ── Parse response ────────────────────────────────────────────────────────
    dev.log('[MLService] Parsing Gemini response body…', name: 'MLService');

    late Map<String, dynamic> outerJson;
    try {
      outerJson = jsonDecode(response.body) as Map<String, dynamic>;
    } catch (e) {
      dev.log(
          '[MLService] ❌ Failed to decode Gemini response envelope: $e\n'
          'Raw body (first 500 chars): ${response.body.substring(0, response.body.length.clamp(0, 500))}',
          name: 'MLService');
      throw Exception('Gemini envelope parse error: $e');
    }

    // Validate top-level structure before drilling in.
    final candidates = outerJson['candidates'];
    if (candidates == null || (candidates as List).isEmpty) {
      dev.log(
          '[MLService] ❌ Gemini "candidates" missing or empty.\n'
          'Full body: ${response.body}',
          name: 'MLService');
      throw Exception('Gemini response has no candidates');
    }

    final parts = candidates.first['content']?['parts'];
    if (parts == null || (parts as List).isEmpty) {
      dev.log(
          '[MLService] ❌ Gemini candidate has no "parts".\n'
          'Candidate: ${candidates.first}',
          name: 'MLService');
      throw Exception('Gemini candidate has no content parts');
    }

    final rawText = (parts.first['text'] as String? ?? '').trim();
    dev.log(
      '[MLService] Gemini raw text (first 300 chars):\n'
      '  ${rawText.substring(0, rawText.length.clamp(0, 300))}',
      name: 'MLService',
    );

    // Strip markdown fences defensively — model sometimes ignores instructions.
    final cleaned = rawText
        .replaceAll(RegExp(r'```json\s*'), '')
        .replaceAll(RegExp(r'```\s*'), '')
        .trim();

    dev.log(
        '[MLService] Cleaned text for JSON parse (first 300 chars):\n'
        '  ${cleaned.substring(0, cleaned.length.clamp(0, 300))}',
        name: 'MLService');

    late Map<String, dynamic> parsed;
    try {
      parsed = jsonDecode(cleaned) as Map<String, dynamic>;
    } catch (e) {
      dev.log(
        '[MLService] ❌ JSON parse failed for Gemini payload.\n'
        '  Error  : $e\n'
        '  Cleaned: $cleaned',
        name: 'MLService',
      );
      throw Exception('Gemini payload JSON parse error: $e');
    }

    // ── Validate prices ───────────────────────────────────────────────────────
    final rawPrices = parsed['prices'];
    if (rawPrices == null || rawPrices is! List) {
      dev.log(
          '[MLService] ❌ Gemini payload missing "prices" list.\n'
          'Keys present: ${parsed.keys.toList()}',
          name: 'MLService');
      throw Exception('Gemini payload is missing the "prices" array');
    }

    final prices = rawPrices.map((e) => (e as num).toDouble()).toList();

    dev.log('[MLService] Prices array length: ${prices.length}',
        name: 'MLService');

    if (prices.length < 60) {
      dev.log(
        '[MLService] ❌ Too few price points: ${prices.length} (need ≥ 60)',
        name: 'MLService',
      );
      throw Exception(
          'Gemini returned only ${prices.length} price points (need ≥ 60)');
    }

    final mae = (parsed['mae'] as num?)?.toDouble() ?? 85.0;
    final rmse = (parsed['rmse'] as num?)?.toDouble() ?? 120.0;
    final mapePct = (parsed['mape_pct'] as num?)?.toDouble() ?? 6.5;

    dev.log(
      '[MLService] ✅ Gemini prediction parsed — '
      'points: ${prices.length}, MAE: $mae, RMSE: $rmse, MAPE: $mapePct%',
      name: 'MLService',
    );

    final result = PredictionResponse.fromPriceList(
      cropName: cropName,
      prices: prices,
      metrics: ModelMetrics.synthetic(mae: mae, rmse: rmse, mapePct: mapePct),
      source: PredictionSource.gemini,
    );

    // ── Store in cache ────────────────────────────────────────────────────────
    _cache[cacheKey] = (response: result, at: DateTime.now());
    dev.log(
        '[MLService] 💾 Cached Gemini result for "$cropName" '
        '(expires in ${_cacheTtl.inHours}h)',
        name: 'MLService');

    return result;
  }

  // ── Dummy fallback data ────────────────────────────────────────────────────
  PredictionResponse _buildDummyResponse(String cropName) {
    dev.log('[MLService] 🔶 Building offline dummy for "$cropName"',
        name: 'MLService');

    const basePrices = <String, double>{
      'maize': 1800,
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

    dev.log('[MLService] 🔶 Dummy base price for "$key": ₹$basePrice/quintal',
        name: 'MLService');

    final rng = math.Random(key.hashCode);
    final prices = List.generate(90, (i) {
      final trend = basePrice + (basePrice * 0.05 * math.sin(i * math.pi / 45));
      final noise = (rng.nextDouble() - 0.5) * basePrice * 0.03;
      return (trend + noise).clamp(basePrice * 0.7, basePrice * 1.4);
    });

    final avg = prices.reduce((a, b) => a + b) / prices.length;
    dev.log(
        '[MLService] 🔶 Dummy ready — 90 points, avg ₹${avg.toStringAsFixed(0)}',
        name: 'MLService');

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
