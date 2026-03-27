import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/crop_provider.dart';

/// Shows model accuracy derived from the real backend MAPE metric.
class AccuracyIndicator extends StatelessWidget {
  const AccuracyIndicator({super.key});

  @override
  Widget build(BuildContext context) {
    return Consumer<CropProvider>(
      builder: (context, provider, _) {
        final response = provider.predictionResponse;
        if (response == null) return const SizedBox.shrink();

        final accuracy = response.accuracyPct;
        final color = response.accuracyColor;
        final label = response.accuracyLabel;
        final icon = accuracy >= 90
            ? Icons.check_circle
            : accuracy >= 70
                ? Icons.info
                : Icons.warning;

        return Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: color.withOpacity(0.3)),
          ),
          child: Row(
            children: [
              Icon(icon, color: color, size: 20),
              const SizedBox(width: 8),
              Text(label,
                  style: TextStyle(
                      fontWeight: FontWeight.bold, color: color, fontSize: 14)),
              const SizedBox(width: 6),
              Text('${accuracy.toStringAsFixed(1)}%',
                  style: TextStyle(
                      fontWeight: FontWeight.w500, color: color, fontSize: 14)),
              const Spacer(),
              Tooltip(
                message: 'Accuracy = 100% − MAPE (${response.metrics.mapePct.toStringAsFixed(1)}%)',
                child: Icon(Icons.help_outline, size: 16, color: Colors.grey[600]),
              ),
            ],
          ),
        );
      },
    );
  }
}
