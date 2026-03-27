import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/crop_model.dart';

class MLService {
  // ── Change this to your machine's LAN IP when testing on a real device ──
  // e.g. 'http://192.168.1.16:5000'
  static const String baseUrl = 'http://192.168.1.16:5000';

  // ─────────────────────────────────────────────────────────────────────────
  // Fetch the list of available crops from the backend
  // ─────────────────────────────────────────────────────────────────────────
  Future<List<String>> fetchAvailableCrops() async {
    final uri = Uri.parse('$baseUrl/api/crops');
    final response = await http.get(uri).timeout(const Duration(seconds: 10));

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      return List<String>.from(data['crops'] as List);
    }
    throw Exception('Failed to load crop list: ${response.statusCode}');
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Fetch 90-day prediction for a given crop
  //
  // First call per crop trains the model (1-5 min).
  // Subsequent calls use the cached model (instant).
  // ─────────────────────────────────────────────────────────────────────────
  Future<PredictionResponse> fetchPredictions(String cropName) async {
    final uri = Uri.parse('$baseUrl/api/predict');
    final response = await http
        .post(
          uri,
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'crop': cropName.toLowerCase()}),
        )
        .timeout(const Duration(minutes: 10)); // allow time for model training

    if (response.statusCode == 200) {
      return PredictionResponse.fromJson(
        jsonDecode(response.body) as Map<String, dynamic>,
      );
    }

    final errorBody = jsonDecode(response.body) as Map<String, dynamic>;
    throw Exception(errorBody['error'] ?? 'Prediction failed');
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Health check
  // ─────────────────────────────────────────────────────────────────────────
  Future<bool> isServerReachable() async {
    try {
      final response = await http
          .get(Uri.parse('$baseUrl/api/health'))
          .timeout(const Duration(seconds: 5));
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }
}
