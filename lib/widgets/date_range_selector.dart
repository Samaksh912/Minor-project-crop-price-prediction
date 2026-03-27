import 'package:flutter/material.dart';

class DateRangeSelector extends StatefulWidget {
  final DateTime? initialStartDate;
  final DateTime? initialEndDate;
  final Function(DateTime, DateTime) onDateRangeSelected;

  const DateRangeSelector({
    super.key,
    this.initialStartDate,
    this.initialEndDate,
    required this.onDateRangeSelected,
  });

  @override
  State<DateRangeSelector> createState() => _DateRangeSelectorState();
}

class _DateRangeSelectorState extends State<DateRangeSelector> {
  late DateTime _startDate;
  late DateTime _endDate;
  String _selectedPreset = 'custom';

  @override
  void initState() {
    super.initState();
    _startDate = widget.initialStartDate ?? DateTime.now();
    _endDate = widget.initialEndDate ?? DateTime.now().add(const Duration(days: 21));
  }

  void _selectPreset(String preset, int days) {
    setState(() {
      _selectedPreset = preset;
      _startDate = DateTime.now();
      _endDate = DateTime.now().add(Duration(days: days));
    });
  }

  Future<void> _pickCustomDate() async {
    final DateTimeRange? picked = await showDateRangePicker(
      context: context,
      firstDate: DateTime.now(),
      lastDate: DateTime.now().add(const Duration(days: 365)),
      initialDateRange: DateTimeRange(start: _startDate, end: _endDate),
    );

    if (picked != null) {
      setState(() {
        _selectedPreset = 'custom';
        _startDate = picked.start;
        _endDate = picked.end;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final daysRange = _endDate.difference(_startDate).inDays;
    
    // Determine accuracy based on range
    String accuracyText;
    Color accuracyColor;
    if (daysRange <= 21) {
      accuracyText = 'High Accuracy (>90%)';
      accuracyColor = const Color(0xFF2E7D32);
    } else if (daysRange <= 42) {
      accuracyText = 'Moderate Accuracy (~60%)';
      accuracyColor = const Color(0xFFF57C00);
    } else {
      accuracyText = 'Low Accuracy (<30%)';
      accuracyColor = const Color(0xFFD32F2F);
    }

    return Container(
      padding: const EdgeInsets.all(24),
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Select Date Range',
            style: TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 20),
          _buildPresetButton(
            'Next 3 Weeks',
            '3weeks',
            21,
            'High Accuracy (>90%)',
            const Color(0xFF2E7D32),
          ),
          const SizedBox(height: 12),
          _buildPresetButton(
            'Next 6 Weeks',
            '6weeks',
            42,
            'Moderate Accuracy (~60%)',
            const Color(0xFFF57C00),
          ),
          const SizedBox(height: 12),
          _buildPresetButton(
            'Next 3 Months',
            '3months',
            90,
            'Low Accuracy (<30%)',
            const Color(0xFFD32F2F),
          ),
          const SizedBox(height: 12),
          OutlinedButton(
            onPressed: _pickCustomDate,
            style: OutlinedButton.styleFrom(
              minimumSize: const Size(double.infinity, 56),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
              side: BorderSide(
                color: _selectedPreset == 'custom'
                    ? Theme.of(context).colorScheme.primary
                    : Colors.grey[300]!,
                width: _selectedPreset == 'custom' ? 2 : 1,
              ),
            ),
            child: const Text('Custom Date Range'),
          ),
          const SizedBox(height: 20),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: accuracyColor.withOpacity(0.1),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: accuracyColor.withOpacity(0.3)),
            ),
            child: Row(
              children: [
                Icon(Icons.info_outline, color: accuracyColor),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        accuracyText,
                        style: TextStyle(
                          fontWeight: FontWeight.bold,
                          color: accuracyColor,
                        ),
                      ),
                      Text(
                        '$daysRange days selected',
                        style: TextStyle(
                          fontSize: 12,
                          color: Colors.grey[700],
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),
          SizedBox(
            width: double.infinity,
            height: 48,
            child: ElevatedButton(
              onPressed: () {
                widget.onDateRangeSelected(_startDate, _endDate);
                Navigator.pop(context);
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: Theme.of(context).colorScheme.primary,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
              child: const Text(
                'Apply',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPresetButton(
    String label,
    String preset,
    int days,
    String accuracy,
    Color color,
  ) {
    final isSelected = _selectedPreset == preset;
    
    return OutlinedButton(
      onPressed: () => _selectPreset(preset, days),
      style: OutlinedButton.styleFrom(
        minimumSize: const Size(double.infinity, 56),
        backgroundColor: isSelected ? color.withOpacity(0.1) : Colors.white,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
        side: BorderSide(
          color: isSelected ? color : Colors.grey[300]!,
          width: isSelected ? 2 : 1,
        ),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: TextStyle(
              color: isSelected ? color : Colors.black87,
              fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
            ),
          ),
          Text(
            accuracy,
            style: TextStyle(
              fontSize: 12,
              color: color,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }
}
