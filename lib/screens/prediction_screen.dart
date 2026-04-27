import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import 'package:fl_chart/fl_chart.dart';
import 'dart:ui';
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
  int _activeMonth = -1;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      Provider.of<CropProvider>(context, listen: false)
          .getPredictions(widget.crop.name, DateTime.now(), DateTime.now());
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF5F7FA),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 1000),
          child: Consumer<CropProvider>(
            builder: (context, provider, _) {
              return CustomScrollView(
                physics: const BouncingScrollPhysics(),
                slivers: [
                  _buildAppBar(),
                  if (provider.isLoading)
                    const SliverFillRemaining(
                      child: Center(
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            CircularProgressIndicator(color: Color(0xFF2E7D32)),
                            SizedBox(height: 24),
                            Text(
                              'Analyzing market trends...',
                              style: TextStyle(
                                  fontSize: 16,
                                  fontWeight: FontWeight.w600,
                                  color: Colors.black54),
                            ),
                          ],
                        ),
                      ),
                    )
                  else if (provider.errorMessage != null)
                    SliverFillRemaining(
                      child: Center(
                        child: Padding(
                          padding: const EdgeInsets.all(32),
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Icon(Icons.error_outline_rounded,
                                  size: 80, color: Colors.red.shade300),
                              const SizedBox(height: 20),
                              Text(provider.errorMessage!,
                                  textAlign: TextAlign.center,
                                  style: const TextStyle(
                                      fontSize: 16, color: Colors.black87)),
                              const SizedBox(height: 32),
                              ElevatedButton.icon(
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: const Color(0xFF2E7D32),
                                  foregroundColor: Colors.white,
                                  padding: const EdgeInsets.symmetric(
                                      horizontal: 24, vertical: 12),
                                  shape: RoundedRectangleBorder(
                                      borderRadius: BorderRadius.circular(16)),
                                ),
                                icon: const Icon(Icons.refresh_rounded),
                                label: const Text('Retry Analysis',
                                    style:
                                        TextStyle(fontWeight: FontWeight.bold)),
                                onPressed: () => provider.getPredictions(
                                    widget.crop.name,
                                    DateTime.now(),
                                    DateTime.now()),
                              ),
                            ],
                          ),
                        ),
                      ),
                    )
                  else if (provider.predictionResponse == null)
                    const SliverFillRemaining(
                        child: Center(child: Text('No data available.')))
                  else ...[
                    SliverToBoxAdapter(
                      child: _HeaderCard(
                          response: provider.predictionResponse!,
                          crop: widget.crop),
                    ),
                    SliverToBoxAdapter(
                      child: Padding(
                        padding: const EdgeInsets.fromLTRB(20, 24, 20, 12),
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            const Text(
                              'Forecast Timeline',
                              style: TextStyle(
                                  fontSize: 20,
                                  fontWeight: FontWeight.w800,
                                  letterSpacing: -0.5),
                            ),
                            Container(
                              decoration: BoxDecoration(
                                  color: Colors.white,
                                  borderRadius: BorderRadius.circular(20),
                                  boxShadow: [
                                    BoxShadow(
                                      color: Colors.black.withOpacity(0.04),
                                      blurRadius: 10,
                                      offset: const Offset(0, 4),
                                    )
                                  ]),
                              child: Row(
                                children: [
                                  _buildToggleBtn(Icons.show_chart_rounded,
                                      _showChart, true),
                                  _buildToggleBtn(
                                      Icons.format_list_bulleted_rounded,
                                      !_showChart,
                                      false),
                                ],
                              ),
                            )
                          ],
                        ),
                      ),
                    ),
                    SliverToBoxAdapter(
                      child: _MonthlyCards(
                        response: provider.predictionResponse!,
                        activeMonth: _activeMonth,
                        onMonthTap: (m) => setState(() {
                          _activeMonth = _activeMonth == m ? -1 : m;
                        }),
                      ),
                    ),
                    SliverToBoxAdapter(
                      child: _showChart
                          ? _ChartSection(
                              points: _getVisiblePoints(
                                  provider.predictionResponse!),
                              unit: provider.predictionResponse!.unit,
                            )
                          : _ListSection(
                              points: _getVisiblePoints(
                                  provider.predictionResponse!),
                              unit: provider.predictionResponse!.unit,
                            ),
                    ),
                    const SliverPadding(padding: EdgeInsets.only(bottom: 40)),
                  ],
                ],
              );
            },
          ),
        ),
      ),
    );
  }

  Widget _buildToggleBtn(IconData icon, bool isActive, bool isLeft) {
    return GestureDetector(
      onTap: () {
        if (!isActive) setState(() => _showChart = !_showChart);
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: isActive ? const Color(0xFF2E7D32) : Colors.transparent,
          borderRadius: BorderRadius.horizontal(
            left: Radius.circular(isLeft ? 20 : 0),
            right: Radius.circular(isLeft ? 0 : 20),
          ),
        ),
        child: Icon(
          icon,
          size: 20,
          color: isActive ? Colors.white : Colors.grey.shade400,
        ),
      ),
    );
  }

  List<PredictionPoint> _getVisiblePoints(PredictionResponse response) {
    if (_activeMonth == -1) return response.predictions;
    final start = _activeMonth * 30;
    final end = (start + 30).clamp(0, response.predictions.length);
    return response.predictions.sublist(start, end);
  }

  Widget _buildAppBar() {
    return SliverAppBar(
      expandedHeight: 240.0,
      pinned: true,
      elevation: 0,
      backgroundColor: Colors.white,
      surfaceTintColor: Colors.transparent,
      leading: Padding(
        padding: const EdgeInsets.all(8.0),
        child: Container(
          decoration: BoxDecoration(
            color: Colors.white.withOpacity(0.8),
            shape: BoxShape.circle,
          ),
          child: IconButton(
            icon: const Icon(Icons.arrow_back_ios_new_rounded,
                size: 20, color: Colors.black87),
            onPressed: () => Navigator.pop(context),
          ),
        ),
      ),
      flexibleSpace: FlexibleSpaceBar(
        centerTitle: true,
        title: Text(
          widget.crop.displayName,
          style: const TextStyle(
            color: Colors.black87,
            fontWeight: FontWeight.w800,
            letterSpacing: -0.5,
          ),
        ),
        background: Stack(
          fit: StackFit.expand,
          children: [
            Container(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [Colors.green.shade50, Colors.teal.shade50],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
              ),
            ),
            Positioned(
              right: -80,
              top: -20,
              child: Container(
                width: 250,
                height: 250,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: Colors.white.withOpacity(0.4),
                ),
              ),
            ),
            Center(
              child: Hero(
                tag: 'crop_icon_${widget.crop.name}',
                child: Container(
                  padding: const EdgeInsets.all(24),
                  decoration: BoxDecoration(
                    color: Colors.white.withOpacity(0.6),
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withOpacity(0.05),
                        blurRadius: 20,
                        offset: const Offset(0, 10),
                      )
                    ],
                  ),
                  child: Text(
                    widget.crop.imageUrl,
                    style: const TextStyle(
                        fontSize: 80, decoration: TextDecoration.none),
                  ),
                ),
              ),
            ),
            ClipRRect(
              child: BackdropFilter(
                filter: ImageFilter.blur(sigmaX: 5, sigmaY: 5),
                child: Container(color: Colors.transparent),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _HeaderCard extends StatelessWidget {
  final PredictionResponse response;
  final Crop crop;
  const _HeaderCard({required this.response, required this.crop});

  @override
  Widget build(BuildContext context) {
    final priceFmt = NumberFormat('#,##0', 'en_IN');
    final dateFmt = DateFormat('dd MMM yyyy');

    return Container(
      margin: const EdgeInsets.fromLTRB(16, 24, 16, 8),
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(28),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.03),
            blurRadius: 24,
            offset: const Offset(0, 12),
          ),
        ],
        border: Border.all(color: Colors.white, width: 2),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Expected Average',
                        style: TextStyle(
                            fontSize: 14,
                            color: Colors.black54,
                            fontWeight: FontWeight.w600)),
                    const SizedBox(height: 4),
                    Text(
                      '₹${priceFmt.format(response.summary.avgPrice)}',
                      style: const TextStyle(
                          fontSize: 36,
                          fontWeight: FontWeight.w800,
                          letterSpacing: -1,
                          color: Color(0xFF1B5E20)),
                    ),
                    Text('per ${response.unit}',
                        style: TextStyle(
                            fontSize: 13,
                            color: Colors.grey.shade500,
                            fontWeight: FontWeight.w500)),
                  ],
                ),
              ),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [
                      response.accuracyColor.withOpacity(0.15),
                      response.accuracyColor.withOpacity(0.05)
                    ],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(
                      color: response.accuracyColor.withOpacity(0.5),
                      width: 1.5),
                ),
                child: Column(
                  children: [
                    Icon(Icons.check_circle_rounded,
                        color: response.accuracyColor, size: 24),
                    const SizedBox(height: 4),
                    Text(
                      '${response.accuracyPct.toStringAsFixed(1)}%',
                      style: TextStyle(
                          color: response.accuracyColor,
                          fontWeight: FontWeight.w800,
                          fontSize: 16),
                    ),
                    Text('Confidence',
                        style: TextStyle(
                            fontSize: 10,
                            color: response.accuracyColor.withOpacity(0.8),
                            fontWeight: FontWeight.bold)),
                  ],
                ),
              ),
            ],
          ),
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 20),
            child: Divider(height: 1, color: Color(0xFFF0F0F0)),
          ),
          Row(
            children: [
              _StatChip(
                  icon: Icons.trending_down_rounded,
                  label: 'Min Price',
                  value: '₹${priceFmt.format(response.summary.minPrice)}',
                  color: Colors.orange.shade700),
              const SizedBox(width: 12),
              _StatChip(
                  icon: Icons.trending_up_rounded,
                  label: 'Max Price',
                  value: '₹${priceFmt.format(response.summary.maxPrice)}',
                  color: Colors.green.shade700),
            ],
          ),
          const SizedBox(height: 20),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: const Color(0xFFF8F9FA),
              borderRadius: BorderRadius.circular(16),
            ),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(12),
                      boxShadow: [
                        BoxShadow(
                            color: Colors.black.withOpacity(0.02),
                            blurRadius: 4)
                      ]),
                  child: const Icon(Icons.calendar_month_rounded,
                      size: 20, color: Color(0xFF2E7D32)),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Forecast Window',
                          style: TextStyle(
                              fontSize: 11,
                              color: Colors.grey.shade500,
                              fontWeight: FontWeight.bold)),
                      Text(
                          '${dateFmt.format(response.predictions.first.date)} - ${dateFmt.format(response.predictions.last.date)}',
                          style: const TextStyle(
                              fontSize: 13,
                              fontWeight: FontWeight.w600,
                              color: Colors.black87)),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _StatChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final Color color;
  const _StatChip(
      {required this.icon,
      required this.label,
      required this.value,
      required this.color});

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: color.withOpacity(0.05),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: color.withOpacity(0.1), width: 1),
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(
            children: [
              Icon(icon, size: 16, color: color),
              const SizedBox(width: 6),
              Text(label,
                  style: TextStyle(
                      fontSize: 12,
                      color: color.withOpacity(0.8),
                      fontWeight: FontWeight.w700)),
            ],
          ),
          const SizedBox(height: 8),
          Text(value,
              style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w800,
                  color: color,
                  letterSpacing: -0.5)),
        ]),
      ),
    );
  }
}

class _MonthlyCards extends StatelessWidget {
  final PredictionResponse response;
  final int activeMonth;
  final ValueChanged<int> onMonthTap;

  const _MonthlyCards(
      {required this.response,
      required this.activeMonth,
      required this.onMonthTap});

  @override
  Widget build(BuildContext context) {
    final priceFmt = NumberFormat('#,##0', 'en_IN');
    final avgs = [
      response.summary.month1Avg,
      response.summary.month2Avg,
      response.summary.month3Avg
    ];
    final labels = ['First 30 Days', 'Next 30 Days', 'Final 30 Days'];

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Row(
        children: List.generate(3, (i) {
          final avg = avgs[i];
          final isActive = activeMonth == i;
          return Expanded(
            child: GestureDetector(
              onTap: () => onMonthTap(i),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 300),
                curve: Curves.easeOutCubic,
                margin: const EdgeInsets.symmetric(horizontal: 4),
                padding:
                    const EdgeInsets.symmetric(vertical: 16, horizontal: 8),
                decoration: BoxDecoration(
                  gradient: isActive
                      ? const LinearGradient(
                          colors: [Color(0xFF2E7D32), Color(0xFF1B5E20)],
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                        )
                      : const LinearGradient(
                          colors: [Colors.white, Colors.white]),
                  borderRadius: BorderRadius.circular(20),
                  boxShadow: isActive
                      ? [
                          BoxShadow(
                              color: const Color(0xFF2E7D32).withOpacity(0.4),
                              blurRadius: 16,
                              offset: const Offset(0, 8))
                        ]
                      : [
                          BoxShadow(
                              color: Colors.black.withOpacity(0.03),
                              blurRadius: 10,
                              offset: const Offset(0, 4))
                        ],
                  border: Border.all(
                      color:
                          isActive ? Colors.transparent : Colors.grey.shade200,
                      width: 1.5),
                ),
                child: Column(
                  children: [
                    Text(labels[i],
                        style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.bold,
                            color: isActive
                                ? Colors.white70
                                : Colors.grey.shade500)),
                    const SizedBox(height: 8),
                    Text(
                      avg != null ? '₹${priceFmt.format(avg)}' : '—',
                      style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w800,
                          color: isActive ? Colors.white : Colors.black87,
                          letterSpacing: -0.5),
                    ),
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

    final spots = List.generate(
        points.length, (i) => FlSpot(i.toDouble(), points[i].price));

    return Container(
      margin: const EdgeInsets.fromLTRB(16, 24, 16, 8),
      padding: const EdgeInsets.fromLTRB(16, 24, 24, 16),
      height: 320,
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(28),
        boxShadow: [
          BoxShadow(
              color: Colors.black.withOpacity(0.04),
              blurRadius: 24,
              offset: const Offset(0, 12))
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(left: 8, bottom: 24),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                      color: const Color(0xFFE8F5E9),
                      borderRadius: BorderRadius.circular(10)),
                  child: const Icon(Icons.auto_graph_rounded,
                      size: 18, color: Color(0xFF2E7D32)),
                ),
                const SizedBox(width: 12),
                Text('Price Trend ($unit)',
                    style: const TextStyle(
                        fontWeight: FontWeight.w800,
                        fontSize: 16,
                        color: Colors.black87)),
              ],
            ),
          ),
          Expanded(
            child: LineChart(
              LineChartData(
                gridData: FlGridData(
                  show: true,
                  drawVerticalLine: false,
                  getDrawingHorizontalLine: (v) => FlLine(
                      color: Colors.grey.shade100,
                      strokeWidth: 1.5,
                      dashArray: [4, 4]),
                ),
                borderData: FlBorderData(show: false),
                titlesData: FlTitlesData(
                  leftTitles: AxisTitles(
                    sideTitles: SideTitles(
                      showTitles: true,
                      reservedSize: 60,
                      getTitlesWidget: (value, _) => Padding(
                        padding: const EdgeInsets.only(right: 8.0),
                        child: Text('₹${priceFmt.format(value)}',
                            style: TextStyle(
                                fontSize: 10,
                                color: Colors.grey.shade500,
                                fontWeight: FontWeight.w600)),
                      ),
                    ),
                  ),
                  bottomTitles: AxisTitles(
                    sideTitles: SideTitles(
                      showTitles: true,
                      interval: (points.length / 4).ceilToDouble(),
                      getTitlesWidget: (value, _) {
                        final idx = value.toInt();
                        if (idx < 0 || idx >= points.length)
                          return const SizedBox();
                        return Padding(
                          padding: const EdgeInsets.only(top: 8.0),
                          child: Text(
                              DateFormat('d MMM').format(points[idx].date),
                              style: TextStyle(
                                  fontSize: 10,
                                  color: Colors.grey.shade500,
                                  fontWeight: FontWeight.w600)),
                        );
                      },
                    ),
                  ),
                  topTitles: const AxisTitles(
                      sideTitles: SideTitles(showTitles: false)),
                  rightTitles: const AxisTitles(
                      sideTitles: SideTitles(showTitles: false)),
                ),
                minY: minP * 0.98,
                maxY: maxP * 1.02,
                lineBarsData: [
                  LineChartBarData(
                    spots: spots,
                    isCurved: true,
                    curveSmoothness: 0.4,
                    color: const Color(0xFF2E7D32),
                    barWidth: 4,
                    isStrokeCapRound: true,
                    dotData: const FlDotData(show: false),
                    belowBarData: BarAreaData(
                      show: true,
                      gradient: LinearGradient(
                        colors: [
                          const Color(0xFF2E7D32).withOpacity(0.3),
                          const Color(0xFF2E7D32).withOpacity(0.0)
                        ],
                        begin: Alignment.topCenter,
                        end: Alignment.bottomCenter,
                      ),
                    ),
                  ),
                ],
                lineTouchData: LineTouchData(
                  handleBuiltInTouches: true,
                  getTouchedSpotIndicator:
                      (LineChartBarData barData, List<int> spotIndexes) {
                    return spotIndexes.map((index) {
                      return TouchedSpotIndicatorData(
                        const FlLine(
                            color: Color(0xFF2E7D32),
                            strokeWidth: 2,
                            dashArray: [4, 4]),
                        FlDotData(
                          getDotPainter: (spot, percent, barData, index) =>
                              FlDotCirclePainter(
                            radius: 6,
                            color: Colors.white,
                            strokeWidth: 3,
                            strokeColor: const Color(0xFF2E7D32),
                          ),
                        ),
                      );
                    }).toList();
                  },
                  touchTooltipData: LineTouchTooltipData(
                    tooltipPadding: const EdgeInsets.symmetric(
                        horizontal: 16, vertical: 12),
                    tooltipMargin: 8,
                    getTooltipItems: (spots) => spots.map((s) {
                      final idx = s.x.toInt();
                      final d = idx < points.length
                          ? DateFormat('d MMM yyyy').format(points[idx].date)
                          : '';
                      return LineTooltipItem(
                        '$d\n',
                        TextStyle(
                            color: Colors.white.withOpacity(0.8),
                            fontSize: 11,
                            fontWeight: FontWeight.w600),
                        children: [
                          TextSpan(
                            text: '₹${priceFmt.format(s.y)}',
                            style: const TextStyle(
                                color: Colors.white,
                                fontSize: 16,
                                fontWeight: FontWeight.w800,
                                letterSpacing: -0.5),
                          ),
                        ],
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

class _ListSection extends StatelessWidget {
  final List<PredictionPoint> points;
  final String unit;
  const _ListSection({required this.points, required this.unit});

  @override
  Widget build(BuildContext context) {
    final priceFmt = NumberFormat('#,##,##0.00', 'en_IN');
    final dateFmt = DateFormat('EEE, d MMM yyyy');

    return Container(
      margin: const EdgeInsets.fromLTRB(16, 24, 16, 8),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(28),
        boxShadow: [
          BoxShadow(
              color: Colors.black.withOpacity(0.04),
              blurRadius: 24,
              offset: const Offset(0, 12))
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(28),
        child: Column(
          children: List.generate(points.length, (i) {
            final p = points[i];
            return Container(
              decoration: BoxDecoration(
                border: i != points.length - 1
                    ? Border(
                        bottom:
                            BorderSide(color: Colors.grey.shade100, width: 1))
                    : null,
              ),
              child: ListTile(
                contentPadding:
                    const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
                leading: Container(
                  width: 40,
                  height: 40,
                  decoration: BoxDecoration(
                      color: const Color(0xFFF5F8F5),
                      borderRadius: BorderRadius.circular(12)),
                  child: Center(
                      child: Text('${i + 1}',
                          style: const TextStyle(
                              fontSize: 13,
                              color: Color(0xFF2E7D32),
                              fontWeight: FontWeight.bold))),
                ),
                title: Text(dateFmt.format(p.date),
                    style: const TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                        color: Colors.black87)),
                trailing: Text('₹${priceFmt.format(p.price)}',
                    style: const TextStyle(
                        fontWeight: FontWeight.w800,
                        color: Color(0xFF1B5E20),
                        fontSize: 16,
                        letterSpacing: -0.5)),
              ),
            );
          }),
        ),
      ),
    );
  }
}
