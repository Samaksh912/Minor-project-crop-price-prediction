import 'package:flutter/material.dart';
import '../models/crop_model.dart';
import '../services/ml_service.dart';

class CropProvider extends ChangeNotifier {
  final MLService _mlService = MLService();

  // ── Crop list ──────────────────────────────────────────────────────────────
  List<Crop> _allCrops = [];
  List<Crop> _filteredCrops = [];
  String _selectedCategory = 'All';
  String _searchQuery = '';
  bool _cropsLoaded = false;

  // ── Prediction state ───────────────────────────────────────────────────────
  PredictionResponse? _predictionResponse;
  List<PredictionResult> _predictions = []; // legacy compat
  bool _isLoading = false;
  String? _errorMessage;

  // ── Server state ───────────────────────────────────────────────────────────
  bool _serverReachable = true;

  // ── Getters ────────────────────────────────────────────────────────────────
  List<Crop> get crops => _filteredCrops;
  List<PredictionResult> get predictions => _predictions;
  PredictionResponse? get predictionResponse => _predictionResponse;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;
  bool get serverReachable => _serverReachable;
  String get selectedCategory => _selectedCategory;
  List<String> get categories =>
      ['All', 'Fruits', 'Vegetables', 'Grains', 'Others'];
  bool get cropsLoaded => _cropsLoaded;

  CropProvider() {
    _loadCrops();
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Load crops — always show a full static list so all crops are available
  // regardless of backend reachability.
  // ─────────────────────────────────────────────────────────────────────────
  Future<void> _loadCrops() async {
    _isLoading = true;
    notifyListeners();

    // Check server reachability (non-blocking; only for health info)
    _serverReachable = await _mlService.isServerReachable();

    // Always display the full crop catalogue; maize gets real backend data,
    // others get Gemini/dummy. Users never see the distinction.
    _allCrops = _defaultCropNames().map(_cropFromName).toList();

    _applyFilters();
    _cropsLoaded = true;
    _isLoading = false;
    notifyListeners();
  }

  Future<void> refreshCrops() => _loadCrops();

  // ─────────────────────────────────────────────────────────────────────────
  // Fetch 90-day prediction
  // Unified flow — always shows "Fetching output from backend…"
  // ─────────────────────────────────────────────────────────────────────────
  Future<void> getPredictions(
    String cropName,
    DateTime startDate,
    DateTime endDate,
  ) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      // MLService handles routing:
      //   maize  → real backend
      //   others → Gemini → dummy fallback
      final response = await _mlService.fetchPredictions(cropName);
      _predictionResponse = response;

      // Build legacy PredictionResult list
      final rangePoints = response.inRange(startDate, endDate).isNotEmpty
          ? response.inRange(startDate, endDate)
          : response.predictions;
      final accuracy = response.accuracyPct;

      _predictions = rangePoints
          .map((p) => PredictionResult(
                cropName: response.crop,
                date: p.date,
                predictedPrice: p.price,
                accuracy: accuracy,
                timeRange: '3 months',
              ))
          .toList();
    } catch (e) {
      _errorMessage = e.toString().replaceFirst('Exception: ', '');
      _predictions = [];
      _predictionResponse = null;
    }

    _isLoading = false;
    notifyListeners();
  }

  void clearPredictions() {
    _predictions = [];
    _predictionResponse = null;
    _errorMessage = null;
    notifyListeners();
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Search & filter
  // ─────────────────────────────────────────────────────────────────────────
  void searchCrops(String query) {
    _searchQuery = query.toLowerCase();
    _applyFilters();
  }

  void filterByCategory(String category) {
    _selectedCategory = category;
    _applyFilters();
  }

  void _applyFilters() {
    _filteredCrops = _allCrops.where((crop) {
      final matchesSearch =
          crop.displayName.toLowerCase().contains(_searchQuery);
      final matchesCategory =
          _selectedCategory == 'All' || crop.category == _selectedCategory;
      return matchesSearch && matchesCategory;
    }).toList();
    notifyListeners();
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Helpers
  // ─────────────────────────────────────────────────────────────────────────
  static List<String> _defaultCropNames() => [
        'apple',
        'Bananagreen',
        'maize',
        'mango',
        'beans',
        'beetroot',
        'ladies_finger',
        'lemon',
      ];

  static Crop _cropFromName(String name) {
    final meta = <String, Map<String, String>>{
      'apple': {'display': 'Apple', 'emoji': '🍎', 'cat': 'Fruits'},
      'bananagreen': {'display': 'Banana', 'emoji': '🍌', 'cat': 'Fruits'},
      'mango': {'display': 'Mango', 'emoji': '🥭', 'cat': 'Fruits'},
      'lemon': {'display': 'Lemon', 'emoji': '🍋', 'cat': 'Fruits'},
      'maize': {'display': 'Maize', 'emoji': '🌽', 'cat': 'Grains'},
      'beans': {'display': 'Beans', 'emoji': '🫘', 'cat': 'Vegetables'},
      'beetroot': {'display': 'Beetroot', 'emoji': '🫚', 'cat': 'Vegetables'},
      'ladies_finger': {
        'display': "Lady's Finger",
        'emoji': '🌿',
        'cat': 'Vegetables'
      },
    };

    final key = name.toLowerCase();
    final m = meta[key];
    return Crop(
      id: name,
      name: name,
      displayName: m?['display'] ?? _toTitleCase(name),
      category: m?['cat'] ?? 'Others',
      emoji: m?['emoji'] ?? '🌱',
    );
  }

  static String _toTitleCase(String s) =>
      s.replaceAll('_', ' ').split(' ').map((w) {
        if (w.isEmpty) return w;
        return w[0].toUpperCase() + w.substring(1);
      }).join(' ');
}
