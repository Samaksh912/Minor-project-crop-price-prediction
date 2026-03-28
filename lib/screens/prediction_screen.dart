import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import 'package:fl_chart/fl_chart.dart';
import '../providers/crop_provider.dart';
import '../models/crop_model.dart';

class PredictionScreen extends StatefulWidget {
  final Crop crop;
  const PredictionScreen({super.key, required this.crop});

  @override
  State<PredictionScreen> createState() => _PredictionScreenState();
}

class _PredictionScreenState extends State<PredictionScreen> {
  bool _showChart = true;
  // Which month window is active (0=month1, 1=month2, 2=month3, -1=all)
  int _activeMonth = -1;

  @override
  void initState() {
    super.initState();
    // Fetch immediately — full 90-day window
    WidgetsBinding.instance.addPostFrameCallback((_) {
      Provider.of<CropProvider>(context, listen: false)
          .getPredictions(widget.crop.name, DateTime.now(), DateTime.now());
    });
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return Scaffold(
      backgroundColor: const Color(0xFFF5F7FA),
      appBar: AppBar(
        title: Text(widget.crop.displayName,
            style: const TextStyle(fontWeight: FontWeight.bold)),
        backgroundColor: cs.primaryContainer,
        actions: [
          IconButton(
            icon: Icon(_showChart ? Icons.list_alt : Icons.show_chart),
            tooltip: _showChart ? 'Show list' : 'Show chart',
            onPressed: () => setState(() => _showChart = !_showChart),
          ),
        ],
      ),
      body: Consumer<CropProvider>(
        builder: (context, provider, _) {
          // ── Loading ───────────────────────────────────────────────────────
          if (provider.isLoading) {
            return Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const CircularProgressIndicator(),
                  const SizedBox(height: 20),
                  const Text(
                    'Fetching output from backend...',
                    style: TextStyle(fontSize: 15, fontWeight: FontWeight.w500),
                  ),
                ],
              ),
            );
          }

          // ── Error ─────────────────────────────────────────────────────────
          if (provider.errorMessage != null) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.error_outline, size: 64, color: Colors.red),
                    const SizedBox(height: 16),
                    Text(provider.errorMessage!,
                        textAlign: TextAlign.center,
                        style: const TextStyle(fontSize: 15)),
                    const SizedBox(height: 24),
                    ElevatedButton.icon(
                      icon: const Icon(Icons.refresh),
                      label: const Text('Retry'),
                      onPressed: () => provider.getPredictions(
                          widget.crop.name, DateTime.now(), DateTime.now()),
                    ),
                  ],
                ),
              ),
            );
          }

          // ── No data yet ───────────────────────────────────────────────────
          final response = provider.predictionResponse;
          if (response == null) {
            return const Center(child: Text('No predictions available.'));
          }

          // ── Filter to selected month or show all ──────────────────────────
          List<PredictionPoint> visiblePoints;
          if (_activeMonth == -1) {
            visiblePoints = response.predictions;
          } else {
            final start = _activeMonth * 30;
            final end = (start + 30).clamp(0, response.predictions.length);
            visiblePoints = response.predictions.sublist(start, end);
          }

          return CustomScrollView(
            slivers: [
              // ── Header: crop info + accuracy ─────────────────────────────
              SliverToBoxAdapter(
                child: _HeaderCard(response: response, crop: widget.crop),
              ),
              // ── Monthly summary cards ─────────────────────────────────────
              SliverToBoxAdapter(
                child: _MonthlyCards(
                  response: response,
                  activeMonth: _activeMonth,
                  onMonthTap: (m) => setState(() {
                    _activeMonth = _activeMonth == m ? -1 : m;
                  }),
                ),
              ),
              // ── Chart or List ─────────────────────────────────────────────
              SliverToBoxAdapter(
                child: _showChart
                    ? _ChartSection(points: visiblePoints, unit: response.unit)
                    : _ListSection(points: visiblePoints, unit: response.unit),
              ),
              const SliverPadding(padding: EdgeInsets.only(bottom: 32)),
            ],
          );
        },
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Header Card
// ─────────────────────────────────────────────────────────────────────────────
class _HeaderCard extends StatelessWidget {
  final PredictionResponse response;
  final Crop crop;
  const _HeaderCard({required this.response, required this.crop});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final priceFmt = NumberFormat('#,##0', 'en_IN');
    final dateFmt = DateFormat('dd MMM yyyy');

    return Container(
      margin: const EdgeInsets.fromLTRB(16, 16, 16, 8),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [cs.primaryContainer, cs.secondaryContainer],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: Colors.green.withOpacity(0.15),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(crop.emoji, style: const TextStyle(fontSize: 40)),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(crop.displayName,
                        style: const TextStyle(
                            fontSize: 22, fontWeight: FontWeight.bold)),
                    Text('90-day price forecast · ${response.unit}',
                        style: TextStyle(fontSize: 13, color: Colors.grey[700])),
                  ],
                ),
              ),
              // Accuracy badge
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: response.accuracyColor.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: response.accuracyColor, width: 1.5),
                ),
                child: Text(
                  '${response.accuracyPct.toStringAsFixed(1)}% accurate',
                  style: TextStyle(
                      color: response.accuracyColor,
                      fontWeight: FontWeight.bold,
                      fontSize: 12),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          // Summary row
          Row(
            children: [
              _StatChip(
                  label: 'Min',
                  value: '₹${priceFmt.format(response.summary.minPrice)}'),
              const SizedBox(width: 8),
              _StatChip(
                  label: 'Avg',
                  value: '₹${priceFmt.format(response.summary.avgPrice)}',
                  highlighted: true),
              const SizedBox(width: 8),
              _StatChip(
                  label: 'Max',
                  value: '₹${priceFmt.format(response.summary.maxPrice)}'),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              const Icon(Icons.calendar_today, size: 14, color: Colors.grey),
              const SizedBox(width: 6),
              Text(
                'Last data: ${dateFmt.format(response.lastObservedDate)}   '
                '· Forecast from ${dateFmt.format(response.predictions.first.date)}',
                style: const TextStyle(fontSize: 11, color: Colors.grey),
              ),
            ],
          ),
          const SizedBox(height: 8),
          // Model metrics row
          Row(
            children: [
              _MetricBadge('MAE', '₹${response.metrics.mae.toStringAsFixed(0)}'),
              const SizedBox(width: 8),
              _MetricBadge('RMSE', '₹${response.metrics.rmse.toStringAsFixed(0)}'),
              const SizedBox(width: 8),
              _MetricBadge('MAPE', '${response.metrics.mapePct.toStringAsFixed(1)}%'),
            ],
          ),
        ],
      ),
    );
  }
}

class _StatChip extends StatelessWidget {
  final String label;
  final String value;
  final bool highlighted;
  const _StatChip(
      {required this.label, required this.value, this.highlighted = false});

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 4),
        decoration: BoxDecoration(
          color: highlighted
              ? Theme.of(context).colorScheme.primary.withOpacity(0.12)
              : Colors.white.withOpacity(0.5),
          borderRadius: BorderRadius.circular(10),
        ),
        child: Column(children: [
          Text(label,
              style: const TextStyle(fontSize: 11, color: Colors.grey)),
          const SizedBox(height: 2),
          Text(value,
              style:
                  const TextStyle(fontSize: 13, fontWeight: FontWeight.bold)),
        ]),
      ),
    );
  }
}

class _MetricBadge extends StatelessWidget {
  final String label;
  final String value;
  const _MetricBadge(this.label, this.value);

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.6),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text('$label: $value',
          style: const TextStyle(fontSize: 11, color: Colors.black54)),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Monthly summary cards (Month 1 / 2 / 3)
// ─────────────────────────────────────────────────────────────────────────────
class _MonthlyCards extends StatelessWidget {
  final PredictionResponse response;
  final int activeMonth;
  final ValueChanged<int> onMonthTap;

  const _MonthlyCards({
    required this.response,
    required this.activeMonth,
    required this.onMonthTap,
  });

  @override
  Widget build(BuildContext context) {
    final priceFmt = NumberFormat('#,##0', 'en_IN');
    final avgs = [
      response.summary.month1Avg,
      response.summary.month2Avg,
      response.summary.month3Avg,
    ];
    final labels = ['Month 1', 'Month 2', 'Month 3'];
    final colors = [
      const Color(0xFF1B5E20),
      const Color(0xFF2E7D32),
      const Color(0xFF388E3C),
    ];

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: Row(
        children: List.generate(3, (i) {
          final avg = avgs[i];
          final isActive = activeMonth == i;
          return Expanded(
            child: GestureDetector(
              onTap: () => onMonthTap(i),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                margin: const EdgeInsets.only(right: 6),
                padding:
                    const EdgeInsets.symmetric(vertical: 14, horizontal: 8),
                decoration: BoxDecoration(
                  color: isActive ? colors[i] : Colors.white,
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(
                      color: isActive ? colors[i] : Colors.grey.shade200),
                  boxShadow: isActive
                      ? [
                          BoxShadow(
                              color: colors[i].withOpacity(0.3),
                              blurRadius: 8,
                              offset: const Offset(0, 3))
                        ]
                      : [],
                ),
                child: Column(
                  children: [
                    Text(labels[i],
                        style: TextStyle(
                            fontSize: 11,
                            color: isActive ? Colors.white70 : Colors.grey)),
                    const SizedBox(height: 4),
                    Text(
                      avg != null ? '₹${priceFmt.format(avg)}' : '—',
                      style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.bold,
                          color: isActive ? Colors.white : Colors.black87),
                    ),
                    const SizedBox(height: 2),
                    Text('avg/quintal',
                        style: TextStyle(
                            fontSize: 9,
                            color: isActive ? Colors.white54 : Colors.grey)),
                  ],
                ),
              ),
            ),
          );
        }),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Line Chart
// ─────────────────────────────────────────────────────────────────────────────
class _ChartSection extends StatelessWidget {
  final List<PredictionPoint> points;
  final String unit;
  const _ChartSection({required this.points, required this.unit});

  @override
  Widget build(BuildContext context) {
    if (points.isEmpty) return const SizedBox();

    final prices = points.map((p) => p.price).toList();
    final minP = prices.reduce((a, b) => a < b ? a : b);
    final maxP = prices.reduce((a, b) => a > b ? a : b);
    final priceFmt = NumberFormat('#,##0', 'en_IN');

    final spots = List.generate(points.length,
        (i) => FlSpot(i.toDouble(), points[i].price));

    return Container(
      margin: const EdgeInsets.fromLTRB(16, 8, 16, 8),
      padding: const EdgeInsets.fromLTRB(12, 20, 20, 12),
      height: 280,
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
        boxShadow: [
          BoxShadow(
              color: Colors.black.withOpacity(0.06),
              blurRadius: 10,
              offset: const Offset(0, 4)),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(left: 8, bottom: 12),
            child: Text('Price Trend ($unit)',
                style: const TextStyle(
                    fontWeight: FontWeight.bold, fontSize: 14)),
          ),
          Expanded(
            child: LineChart(
              LineChartData(
                gridData: FlGridData(
                  show: true,
                  drawVerticalLine: false,
                  getDrawingHorizontalLine: (v) => FlLine(
                      color: Colors.grey.shade100, strokeWidth: 1),
                ),
                borderData: FlBorderData(show: false),
                titlesData: FlTitlesData(
                  leftTitles: AxisTitles(
                    sideTitles: SideTitles(
                      showTitles: true,
                      reservedSize: 56,
                      getTitlesWidget: (value, _) => Text(
                        '₹${priceFmt.format(value)}',
                        style: const TextStyle(
                            fontSize: 9, color: Colors.grey),
                      ),
                    ),
                  ),
                  bottomTitles: AxisTitles(
                    sideTitles: SideTitles(
                      showTitles: true,
                      interval: (points.length / 4).ceilToDouble(),
                      getTitlesWidget: (value, _) {
                        final idx = value.toInt();
                        if (idx < 0 || idx >= points.length) {
                          return const SizedBox();
                        }
                        return Text(
                          DateFormat('d MMM').format(points[idx].date),
                          style: const TextStyle(
                              fontSize: 9, color: Colors.grey),
                        );
                      },
                    ),
                  ),
                  topTitles: const AxisTitles(
                      sideTitles: SideTitles(showTitles: false)),
                  rightTitles: const AxisTitles(
                      sideTitles: SideTitles(showTitles: false)),
                ),
                minY: minP * 0.995,
                maxY: maxP * 1.005,
                lineBarsData: [
                  LineChartBarData(
                    spots: spots,
                    isCurved: true,
                    curveSmoothness: 0.35,
                    color: const Color(0xFF2E7D32),
                    barWidth: 2.5,
                    dotData: const FlDotData(show: false),
                    belowBarData: BarAreaData(
                      show: true,
                      gradient: LinearGradient(
                        colors: [
                          const Color(0xFF2E7D32).withOpacity(0.2),
                          const Color(0xFF2E7D32).withOpacity(0.0),
                        ],
                        begin: Alignment.topCenter,
                        end: Alignment.bottomCenter,
                      ),
                    ),
                  ),
                ],
                lineTouchData: LineTouchData(
                  touchTooltipData: LineTouchTooltipData(
                    getTooltipItems: (spots) => spots.map((s) {
                      final idx = s.x.toInt();
                      final d = idx < points.length
                          ? DateFormat('d MMM').format(points[idx].date)
                          : '';
                      return LineTooltipItem(
                        '$d\n₹${priceFmt.format(s.y)}',
                        const TextStyle(
                            color: Colors.white,
                            fontSize: 12,
                            fontWeight: FontWeight.bold),
                      );
                    }).toList(),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// List view
// ─────────────────────────────────────────────────────────────────────────────
class _ListSection extends StatelessWidget {
  final List<PredictionPoint> points;
  final String unit;
  const _ListSection({required this.points, required this.unit});

  @override
  Widget build(BuildContext context) {
    final priceFmt = NumberFormat('#,##,##0.00', 'en_IN');
    final dateFmt = DateFormat('EEE, d MMM yyyy');

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
        boxShadow: [
          BoxShadow(
              color: Colors.black.withOpacity(0.06),
              blurRadius: 10,
              offset: const Offset(0, 4)),
        ],
      ),
      child: Column(
        children: List.generate(points.length, (i) {
          final p = points[i];
          return ListTile(
            dense: true,
            leading: CircleAvatar(
              radius: 14,
              backgroundColor: const Color(0xFF2E7D32).withOpacity(0.1),
              child: Text('${i + 1}',
                  style: const TextStyle(
                      fontSize: 10,
                      color: Color(0xFF2E7D32),
                      fontWeight: FontWeight.bold)),
            ),
            title: Text(dateFmt.format(p.date),
                style: const TextStyle(fontSize: 13)),
            trailing: Text(
              '₹${priceFmt.format(p.price)}',
              style: const TextStyle(
                  fontWeight: FontWeight.bold,
                  color: Color(0xFF1B5E20),
                  fontSize: 14),
            ),
          );
        }),
      ),
    );
  }
}
