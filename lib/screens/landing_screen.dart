import 'dart:ui' as ui;
import 'dart:math' as math;
import 'package:flutter/material.dart';

// --- CONSTANTS & THEME ---
const Color grassGreen = Color(0xFF4CAF50);
const Color lightGreen = Color(0xFF81C784);
const Color soilBrown = Color(0xFF8D6E63);
const Color darkSoil = Color(0xFF6D4C41);
const Color lightBeige = Color(0xFFFDFBF7);
const Color skyBlue = Color(0xFFF0FAFB);

class BestCropApp extends StatelessWidget {
  const BestCropApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Best Crop Price',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.light,
        scaffoldBackgroundColor: lightBeige,
        colorScheme: const ColorScheme.light(
          primary: grassGreen,
          secondary: soilBrown,
          surface: Colors.white,
          background: lightBeige,
        ),
        fontFamily: 'Roboto',
      ),
      home: const LandingScreen(),
    );
  }
}

// --- MAIN LANDING SCREEN ---
class LandingScreen extends StatefulWidget {
  const LandingScreen({super.key});

  @override
  State<LandingScreen> createState() => _LandingScreenState();
}

class _LandingScreenState extends State<LandingScreen> {
  final ScrollController _scrollController = ScrollController();
  final ValueNotifier<double> _scrollNotifier = ValueNotifier(0.0);
  final ValueNotifier<Offset> _mouseNotifier = ValueNotifier(Offset.zero);

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(() {
      _scrollNotifier.value = _scrollController.offset;
    });
  }

  @override
  void dispose() {
    _scrollController.dispose();
    _scrollNotifier.dispose();
    _mouseNotifier.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final size = MediaQuery.of(context).size;
    final vh = math.max(size.height, 100.0); // Guard against Size.zero
    final vw = math.max(size.width, 100.0);

    // Define scroll durations for hijacking - Increased to make scrolling slower and smoother
    final heroDuration = vh * 2.5;
    final featuresDuration = vh * 3.5;
    final visualDuration = vh * 2.5;
    final howItWorksDuration = vh * 2.5;

    // Calculate absolute start offsets
    final heroStart = 0.0;
    final featuresStart = heroDuration + vh;
    final visualStart = featuresStart + featuresDuration + vh;
    final howItWorksStart = visualStart + visualDuration + vh;

    return Scaffold(
        backgroundColor: lightBeige,
        body: MouseRegion(
          cursor: SystemMouseCursors.none,
          onHover: (details) {
            final size = MediaQuery.of(context).size;
            double dx = (details.localPosition.dx / size.width) - 0.5;
            double dy = (details.localPosition.dy / size.height) - 0.5;
            _mouseNotifier.value = Offset(dx, dy);
          },
          child: Stack(
            children: [
              // Dynamic Background blending based on scroll
              Positioned.fill(
                child: ValueListenableBuilder<double>(
                  valueListenable: _scrollNotifier,
                  builder: (context, scrollValue, child) {
                    double progress = howItWorksStart > 0
                        ? (scrollValue / howItWorksStart).clamp(0.0, 1.0)
                        : 0.0;
                    Color? bgColor = Color.lerp(skyBlue, lightBeige, progress);
                    return Container(color: bgColor);
                  },
                ),
              ),

              // Story-Driven Parallax Background Image
              Positioned.fill(
                child: ValueListenableBuilder<double>(
                  valueListenable: _scrollNotifier,
                  builder: (context, scrollValue, child) {
                    final totalScroll = howItWorksStart + howItWorksDuration;
                    double progress = totalScroll > 0
                        ? (scrollValue / totalScroll).clamp(0.0, 1.0)
                        : 0.0;

                    // Pan from top (sky) to bottom (brain)
                    double alignY = -1.0 + (progress * 2.0);

                    return ValueListenableBuilder<Offset>(
                      valueListenable: _mouseNotifier,
                      builder: (context, mouseOffset, child) {
                        return Transform.translate(
                          offset: Offset(
                              -mouseOffset.dx * 30, -mouseOffset.dy * 30),
                          child: Transform.scale(
                            scale: 1.05,
                            child: Opacity(
                              opacity:
                                  1.0, // Fully opaque to show the gorgeous details
                              child: Image.asset(
                                'assets/images/bg.png',
                                fit: BoxFit.cover,
                                alignment: Alignment(0, alignY),
                              ),
                            ),
                          ),
                        );
                      },
                    );
                  },
                ),
              ),

              Positioned.fill(
                child: ListView(
                  controller: _scrollController,
                  physics: const BouncingScrollPhysics(),
                  padding: EdgeInsets.zero,
                  children: [
                    StickyWrapper(
                      scrollNotifier: _scrollNotifier,
                      startOffset: heroStart,
                      stickyDuration: heroDuration,
                      vh: vh,
                      builder: (context, relativeScrollNotifier) => HeroSection(
                          relativeScrollNotifier: relativeScrollNotifier,
                          vh: vh,
                          stickyDuration: heroDuration),
                    ),
                    StickyWrapper(
                      scrollNotifier: _scrollNotifier,
                      startOffset: featuresStart,
                      stickyDuration: featuresDuration,
                      vh: vh,
                      builder: (context, relativeScrollNotifier) =>
                          FeaturesSection(
                              relativeScrollNotifier: relativeScrollNotifier,
                              vh: vh,
                              stickyDuration: featuresDuration),
                    ),
                    StickyWrapper(
                      scrollNotifier: _scrollNotifier,
                      startOffset: visualStart,
                      stickyDuration: visualDuration,
                      vh: vh,
                      builder: (context, relativeScrollNotifier) =>
                          InteractiveVisualSection(
                              relativeScrollNotifier: relativeScrollNotifier,
                              vh: vh,
                              stickyDuration: visualDuration),
                    ),
                    StickyWrapper(
                      scrollNotifier: _scrollNotifier,
                      startOffset: howItWorksStart,
                      stickyDuration: howItWorksDuration,
                      vh: vh,
                      builder: (context, relativeScrollNotifier) =>
                          HowItWorksSection(
                              relativeScrollNotifier: relativeScrollNotifier,
                              vh: vh,
                              stickyDuration: howItWorksDuration),
                    ),
                    SizedBox(
                      height: vh,
                      child: const Center(child: FinalCtaSection()),
                    ),
                  ],
                ),
              ),

              // Leaf trail + custom leaf cursor
              Positioned.fill(
                child: IgnorePointer(
                  child: LeafCursorOverlay(mouseNotifier: _mouseNotifier),
                ),
              ),
            ],
          ),
        ));
  }
}

// --- STICKY WRAPPER ARCHITECTURE ---
class StickyWrapper extends StatelessWidget {
  final ValueNotifier<double> scrollNotifier;
  final double startOffset;
  final double stickyDuration;
  final double vh;
  final Widget Function(
      BuildContext context, ValueNotifier<double> progressNotifier) builder;

  const StickyWrapper({
    super.key,
    required this.scrollNotifier,
    required this.startOffset,
    required this.stickyDuration,
    required this.vh,
    required this.builder,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: stickyDuration + vh,
      child: Align(
        alignment: Alignment.topCenter,
        child: ValueListenableBuilder<double>(
          valueListenable: scrollNotifier,
          builder: (context, scroll, child) {
            double relativeScroll = scroll - startOffset;
            double stickyOffset = relativeScroll.clamp(0.0, stickyDuration);

            return Transform.translate(
              offset: Offset(0, stickyOffset),
              child: SizedBox(
                height: vh,
                width: double.infinity,
                child: child,
              ),
            );
          },
          child: _ProgressProvider(
            scrollNotifier: scrollNotifier,
            startOffset: startOffset,
            stickyDuration: stickyDuration,
            builder: builder,
          ),
        ),
      ),
    );
  }
}

class _ProgressProvider extends StatefulWidget {
  final ValueNotifier<double> scrollNotifier;
  final double startOffset;
  final double stickyDuration;
  final Widget Function(
      BuildContext context, ValueNotifier<double> progressNotifier) builder;

  const _ProgressProvider({
    required this.scrollNotifier,
    required this.startOffset,
    required this.stickyDuration,
    required this.builder,
  });

  @override
  State<_ProgressProvider> createState() => _ProgressProviderState();
}

class _ProgressProviderState extends State<_ProgressProvider> {
  late ValueNotifier<double> relativeScrollNotifier;

  @override
  void initState() {
    super.initState();
    relativeScrollNotifier = ValueNotifier(0.0);
    widget.scrollNotifier.addListener(_updateProgress);
    WidgetsBinding.instance.addPostFrameCallback((_) => _updateProgress());
  }

  void _updateProgress() {
    double relativeScroll = widget.scrollNotifier.value - widget.startOffset;
    if (relativeScrollNotifier.value != relativeScroll) {
      relativeScrollNotifier.value = relativeScroll;
    }
  }

  @override
  void dispose() {
    widget.scrollNotifier.removeListener(_updateProgress);
    relativeScrollNotifier.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return widget.builder(context, relativeScrollNotifier);
  }
}

// --- 1. HERO SECTION (Cinematic Parallax & Camera) ---
class HeroSection extends StatelessWidget {
  final ValueNotifier<double> relativeScrollNotifier;
  final double vh;
  final double stickyDuration;

  const HeroSection(
      {super.key,
      required this.relativeScrollNotifier,
      required this.vh,
      required this.stickyDuration});

  @override
  Widget build(BuildContext context) {
    return RepaintBoundary(
      child: ValueListenableBuilder<double>(
        valueListenable: relativeScrollNotifier,
        builder: (context, relativeScroll, child) {
          double progress = stickyDuration > 0
              ? (relativeScroll / stickyDuration).clamp(0.0, 1.0)
              : 0.0;
          double scale = 1.0 + (progress * 0.4);
          double translateY = progress * vh * 0.5;
          double rotateX = progress * 0.3;
          double opacity = (1 - (progress * 3)).clamp(0.0, 1.0);

          return Transform(
            transform: Matrix4.identity()
              ..setEntry(3, 2, 0.001)
              ..translate(0.0, translateY, 0.0)
              ..rotateX(rotateX)
              ..scale(scale, scale, 1.0),
            alignment: Alignment.center,
            child: ClipPath(
              clipper: OrganicWaveClipper(),
              child: Container(
                color: Colors
                    .transparent, // Let the background sky and sun shine through
                child: Stack(
                  children: [
                    const Positioned.fill(child: FloatingParticles()),
                    Opacity(
                      opacity: opacity,
                      child: SafeArea(
                        child: Center(
                          child: Padding(
                            padding: const EdgeInsets.symmetric(horizontal: 24),
                            child: ClipRRect(
                              borderRadius: BorderRadius.circular(40),
                              child: BackdropFilter(
                                filter:
                                    ui.ImageFilter.blur(sigmaX: 15, sigmaY: 15),
                                child: Container(
                                  padding: const EdgeInsets.symmetric(
                                      horizontal: 40, vertical: 60),
                                  decoration: BoxDecoration(
                                    color: Colors.white
                                        .withOpacity(0.65), // Glassmorphic base
                                    borderRadius: BorderRadius.circular(40),
                                    border: Border.all(
                                        color: Colors.white.withOpacity(0.8),
                                        width: 2),
                                    boxShadow: [
                                      BoxShadow(
                                          color: Colors.black.withOpacity(0.05),
                                          blurRadius: 30)
                                    ],
                                  ),
                                  child: Column(
                                    mainAxisAlignment: MainAxisAlignment.center,
                                    mainAxisSize: MainAxisSize
                                        .min, // PREVENT INFINITE HEIGHT
                                    children: [
                                      Container(
                                        padding: const EdgeInsets.all(24),
                                        decoration: BoxDecoration(
                                            color:
                                                Colors.white.withOpacity(0.8),
                                            shape: BoxShape.circle,
                                            boxShadow: [
                                              BoxShadow(
                                                  color: grassGreen
                                                      .withOpacity(0.2),
                                                  blurRadius: 30)
                                            ]),
                                        child: const Icon(Icons.spa_rounded,
                                            size: 80, color: grassGreen),
                                      ),
                                      const SizedBox(height: 40),
                                      const Text(
                                        "Predicting Tomorrow's\nHarvest Today",
                                        textAlign: TextAlign.center,
                                        style: TextStyle(
                                          fontSize: 56,
                                          height: 1.1,
                                          fontWeight: FontWeight.w900,
                                          color: darkSoil,
                                          letterSpacing: -2,
                                        ),
                                      ),
                                      const SizedBox(height: 24),
                                      const Text(
                                        'Empower your farming decisions with AI-driven\ncrop price forecasts and real-time market trends.',
                                        textAlign: TextAlign.center,
                                        style: TextStyle(
                                            fontSize: 22,
                                            fontWeight: FontWeight.w600,
                                            color: soilBrown),
                                      ),
                                      const SizedBox(height: 60),
                                      MagneticHoverWidget(
                                          child: HeroCtaButton(onTap: () {})),
                                    ],
                                  ),
                                ),
                              ),
                            ),
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}

// --- 2. FEATURES SECTION (Horizontal Scroll) ---
class FeaturesSection extends StatelessWidget {
  final ValueNotifier<double> relativeScrollNotifier;
  final double vh;
  final double stickyDuration;

  const FeaturesSection(
      {super.key,
      required this.relativeScrollNotifier,
      required this.vh,
      required this.stickyDuration});

  @override
  Widget build(BuildContext context) {
    final size = MediaQuery.of(context).size;
    final vw = math.max(size.width, 100.0); // Guard against zero width

    return RepaintBoundary(
      child: Container(
        width: vw,
        height: vh,
        color: Colors.transparent,
        child: Stack(
          children: [
            Positioned(
              top: vh * 0.15,
              left: 0,
              right: 0,
              child: ValueListenableBuilder<double>(
                valueListenable: relativeScrollNotifier,
                builder: (context, relativeScroll, child) {
                  double enterProgress =
                      ((relativeScroll + vh) / vh).clamp(0.0, 1.0);
                  double progress = stickyDuration > 0
                      ? (relativeScroll / stickyDuration).clamp(0.0, 1.0)
                      : 0.0;

                  double opacity =
                      (progress > 0.9) ? (1 - progress) * 10 : enterProgress;
                  double translateY = (1 - enterProgress) * 50;

                  return Opacity(
                    opacity: opacity.clamp(0.0, 1.0),
                    child: Transform.translate(
                      offset: Offset(0, translateY),
                      child: child,
                    ),
                  );
                },
                child: const Column(
                  mainAxisSize: MainAxisSize.min, // PREVENT INFINITE HEIGHT
                  children: [
                    Text(
                      'Empowering Your Harvest',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                          fontSize: 42,
                          fontWeight: FontWeight.w900,
                          color: darkSoil,
                          letterSpacing: -1),
                    ),
                    SizedBox(height: 16),
                    Text(
                      'Everything you need to maximize your agricultural yield and profits.',
                      style: TextStyle(fontSize: 20, color: soilBrown),
                      textAlign: TextAlign.center,
                    ),
                  ],
                ),
              ),
            ),
            Positioned(
              top: vh * 0.35,
              left: 0,
              width: vw *
                  4, // Explicit large width instead of negative right to avoid layout crash
              child: ValueListenableBuilder<double>(
                valueListenable: relativeScrollNotifier,
                builder: (context, relativeScroll, child) {
                  double enterProgress =
                      ((relativeScroll + vh) / vh).clamp(0.0, 1.0);
                  double progress = stickyDuration > 0
                      ? (relativeScroll / stickyDuration).clamp(0.0, 1.0)
                      : 0.0;

                  double maxScroll = vw + 1600;
                  double enterSlide = (1 - enterProgress) * (vw * 0.5);
                  double slideX = enterSlide + (vw - (progress * maxScroll));

                  return Transform.translate(
                    offset: Offset(slideX, 0),
                    child: Opacity(
                      opacity: enterProgress,
                      child: child,
                    ),
                  );
                },
                child: Row(
                  children: [
                    SizedBox(width: vw * 0.2),
                    const HoverTiltWidget(
                        child: FeatureCard(
                            icon: Icons.auto_graph_rounded,
                            title: 'Price Prediction',
                            description:
                                'Machine learning models forecast crop values with high accuracy.',
                            width: 350)),
                    const SizedBox(width: 40),
                    const HoverTiltWidget(
                        child: FeatureCard(
                            icon: Icons.pie_chart_rounded,
                            title: 'Market Trends',
                            description:
                                'Visualize historical data and demand shifts instantly.',
                            width: 350)),
                    const SizedBox(width: 40),
                    const HoverTiltWidget(
                        child: FeatureCard(
                            icon: Icons.cloud_rounded,
                            title: 'Weather Impact',
                            description:
                                'Analyze how upcoming weather patterns affect market shortages.',
                            width: 350)),
                    const SizedBox(width: 40),
                    const HoverTiltWidget(
                        child: FeatureCard(
                            icon: Icons.lightbulb_rounded,
                            title: 'Smart Suggestions',
                            description:
                                'Get tailored advice on when to hold or sell your harvest.',
                            width: 350)),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class FeatureCard extends StatefulWidget {
  final IconData icon;
  final String title;
  final String description;
  final double width;

  const FeatureCard(
      {super.key,
      required this.icon,
      required this.title,
      required this.description,
      required this.width});

  @override
  State<FeatureCard> createState() => _FeatureCardState();
}

class _FeatureCardState extends State<FeatureCard> {
  bool _isHovered = false;

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      onEnter: (_) => setState(() => _isHovered = true),
      onExit: (_) => setState(() => _isHovered = false),
      child: AnimatedScale(
        scale: _isHovered ? 1.05 : 1.0,
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeOutBack,
        child: Container(
          width: widget.width,
          padding: const EdgeInsets.all(40),
          decoration: BoxDecoration(
            color: Colors.white
                .withOpacity(0.85), // Glassmorphic effect over the fields
            borderRadius: BorderRadius.circular(30),
            boxShadow: [
              BoxShadow(
                color: soilBrown.withOpacity(_isHovered ? 0.3 : 0.15),
                blurRadius: _isHovered ? 50 : 25,
                offset: Offset(0, _isHovered ? 25 : 10),
              ),
            ],
            border: Border.all(
                color: _isHovered
                    ? grassGreen.withOpacity(0.5)
                    : Colors.white.withOpacity(0.5),
                width: 2),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                    color: skyBlue, borderRadius: BorderRadius.circular(24)),
                child: Icon(widget.icon, size: 40, color: grassGreen),
              ),
              const SizedBox(height: 32),
              Text(widget.title,
                  style: const TextStyle(
                      fontSize: 26,
                      fontWeight: FontWeight.bold,
                      color: darkSoil)),
              const SizedBox(height: 16),
              Text(widget.description,
                  style: const TextStyle(
                      fontSize: 18, color: soilBrown, height: 1.5)),
            ],
          ),
        ),
      ),
    );
  }
}

// --- 3. INTERACTIVE VISUAL SECTION (Data Visualization) ---
class InteractiveVisualSection extends StatelessWidget {
  final ValueNotifier<double> relativeScrollNotifier;
  final double vh;
  final double stickyDuration;

  const InteractiveVisualSection({
    super.key,
    required this.relativeScrollNotifier,
    required this.vh,
    required this.stickyDuration,
  });

  @override
  Widget build(BuildContext context) {
    return RepaintBoundary(
      child: Container(
        color: Colors.transparent,
        child: ValueListenableBuilder<double>(
          valueListenable: relativeScrollNotifier,
          builder: (context, relativeScroll, child) {
            double enterProgress = ((relativeScroll + vh) / vh).clamp(0.0, 1.0);

            // The core driver for our scroll-hijacked animations
            double progress = stickyDuration > 0
                ? (relativeScroll / stickyDuration).clamp(0.0, 1.0)
                : 0.0;

            // Using a bouncier curve for a dynamic snap-into-place feel
            double eased = Curves.easeOutBack.transform(progress);

            return Opacity(
              opacity: enterProgress,
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  // --- Header ---
                  Opacity(
                    opacity: (enterProgress + eased).clamp(0.0, 1.0),
                    child: Transform.translate(
                      offset: Offset(0, 40 * (1 - eased.clamp(0.0, 1.0))),
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(30),
                        child: BackdropFilter(
                          filter: ui.ImageFilter.blur(sigmaX: 10, sigmaY: 10),
                          child: Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 40, vertical: 24),
                            decoration: BoxDecoration(
                              color: Colors.white.withOpacity(0.85),
                              borderRadius: BorderRadius.circular(30),
                              boxShadow: [
                                BoxShadow(
                                    color: Colors.black.withOpacity(0.12),
                                    blurRadius: 40,
                                    offset: const Offset(0, 16))
                              ],
                              border: Border.all(
                                  color: Colors.white.withOpacity(0.8),
                                  width: 2),
                            ),
                            child: const Column(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Text('Real-time Intelligence',
                                    style: TextStyle(
                                        fontSize: 48,
                                        fontWeight: FontWeight.w900,
                                        color: darkSoil,
                                        letterSpacing: -1)),
                                SizedBox(height: 12),
                                Text('Watch crop prices grow — powered by AI.',
                                    style: TextStyle(
                                        fontSize: 20, color: soilBrown)),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 48),
                  // --- Animated Line Graph driven by scroll ---
                  Opacity(
                    opacity: progress.clamp(0.0, 1.0),
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(32),
                      child: BackdropFilter(
                        filter: ui.ImageFilter.blur(sigmaX: 12, sigmaY: 12),
                        child: Container(
                          width: 780,
                          padding: const EdgeInsets.fromLTRB(40, 32, 40, 40),
                          decoration: BoxDecoration(
                            color: Colors.white.withOpacity(0.88),
                            borderRadius: BorderRadius.circular(32),
                            border: Border.all(
                                color: Colors.white.withOpacity(0.9), width: 2),
                            boxShadow: [
                              BoxShadow(
                                  color: Colors.black.withOpacity(0.08),
                                  blurRadius: 40)
                            ],
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              // Graph header row
                              Row(
                                mainAxisAlignment:
                                    MainAxisAlignment.spaceBetween,
                                children: [
                                  Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      const Text('Crop Price Forecast',
                                          style: TextStyle(
                                              fontSize: 22,
                                              fontWeight: FontWeight.w800,
                                              color: darkSoil)),
                                      const SizedBox(height: 4),
                                      const Text('Next 90 days prediction',
                                          style: TextStyle(
                                              fontSize: 14, color: soilBrown)),
                                    ],
                                  ),
                                  Container(
                                    padding: const EdgeInsets.symmetric(
                                        horizontal: 16, vertical: 8),
                                    decoration: BoxDecoration(
                                      color: grassGreen.withOpacity(0.12),
                                      borderRadius: BorderRadius.circular(20),
                                    ),
                                    child: Row(
                                      children: [
                                        const Icon(Icons.trending_up,
                                            color: grassGreen, size: 18),
                                        const SizedBox(width: 6),
                                        Text(
                                          '+${(progress * 18.5).toStringAsFixed(1)}%',
                                          style: const TextStyle(
                                              fontSize: 18,
                                              fontWeight: FontWeight.w900,
                                              color: grassGreen),
                                        ),
                                      ],
                                    ),
                                  )
                                ],
                              ),
                              const SizedBox(height: 24),
                              // The line graph itself
                              SizedBox(
                                height: 220,
                                child: CustomPaint(
                                  painter:
                                      _GrowthLinePainter(progress: progress),
                                  size: const Size(double.infinity, 220),
                                ),
                              ),
                              const SizedBox(height: 16),
                              // X-axis labels
                              Row(
                                mainAxisAlignment:
                                    MainAxisAlignment.spaceBetween,
                                children: [
                                  'Now',
                                  'Week 1',
                                  'Week 2',
                                  'Week 3',
                                  'Week 4'
                                ]
                                    .map((l) => Text(l,
                                        style: const TextStyle(
                                            fontSize: 12, color: soilBrown)))
                                    .toList(),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            );
          },
        ),
      ),
    );
  }
}

// Growth line graph painter
class _GrowthLinePainter extends CustomPainter {
  final double progress;
  const _GrowthLinePainter({required this.progress});

  // Pre-defined growth data points (normalized 0..1 for Y)
  static const _dataY = [
    0.55,
    0.52,
    0.58,
    0.54,
    0.60,
    0.57,
    0.63,
    0.60,
    0.67,
    0.64,
    0.70,
    0.68,
    0.74,
    0.71,
    0.78,
    0.76,
    0.82,
    0.79,
    0.86,
    0.84,
    0.90
  ];

  @override
  void paint(Canvas canvas, Size size) {
    final int totalPoints = _dataY.length;
    // How many points to draw based on scroll progress
    final double revealedFraction = progress.clamp(0.0, 1.0);
    final double pointsToShow = revealedFraction * (totalPoints - 1);
    final int fullPoints = pointsToShow.floor();
    final double remainder = pointsToShow - fullPoints;

    if (fullPoints < 1) return;

    // Helper: map point index to canvas coordinates
    Offset pt(int i) {
      double x = (i / (totalPoints - 1)) * size.width;
      double y = size.height - (_dataY[i] * size.height);
      return Offset(x, y);
    }

    // Gradient fill path
    final fillPath = Path();
    fillPath.moveTo(0, size.height);
    fillPath.lineTo(pt(0).dx, pt(0).dy);
    for (int i = 1; i <= fullPoints; i++) {
      final p0 = pt(i - 1);
      final p1 = pt(i);
      final ctrl1 = Offset(p0.dx + (p1.dx - p0.dx) * 0.5, p0.dy);
      final ctrl2 = Offset(p0.dx + (p1.dx - p0.dx) * 0.5, p1.dy);
      fillPath.cubicTo(ctrl1.dx, ctrl1.dy, ctrl2.dx, ctrl2.dy, p1.dx, p1.dy);
    }
    // Partial last segment
    if (fullPoints < totalPoints - 1 && remainder > 0) {
      final p0 = pt(fullPoints);
      final p1 = pt(fullPoints + 1);
      final ctrl1 = Offset(p0.dx + (p1.dx - p0.dx) * 0.5, p0.dy);
      final ctrl2 = Offset(p0.dx + (p1.dx - p0.dx) * 0.5, p1.dy);
      final ex = p0.dx + (p1.dx - p0.dx) * remainder;
      final ey = _cubicY(p0.dy, ctrl1.dy, ctrl2.dy, p1.dy, remainder);
      fillPath.cubicTo(
          p0.dx + (ctrl1.dx - p0.dx) * remainder,
          p0.dy + (ctrl1.dy - p0.dy) * remainder,
          ctrl1.dx + (ctrl2.dx - ctrl1.dx) * remainder,
          ctrl1.dy + (ctrl2.dy - ctrl1.dy) * remainder,
          ex,
          ey);
    }
    final lastVisibleX = fullPoints < totalPoints - 1
        ? pt(fullPoints).dx +
            (pt(fullPoints + 1).dx - pt(fullPoints).dx) * remainder
        : pt(fullPoints).dx;
    fillPath.lineTo(lastVisibleX, size.height);
    fillPath.close();

    final fillPaint = Paint()
      ..shader = LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [grassGreen.withOpacity(0.35), grassGreen.withOpacity(0.0)],
      ).createShader(Rect.fromLTWH(0, 0, size.width, size.height))
      ..style = PaintingStyle.fill;
    canvas.drawPath(fillPath, fillPaint);

    // Draw the stroke line
    final linePaint = Paint()
      ..color = grassGreen
      ..strokeWidth = 3.5
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;

    final linePath = Path();
    linePath.moveTo(pt(0).dx, pt(0).dy);
    for (int i = 1; i <= fullPoints; i++) {
      final p0 = pt(i - 1);
      final p1 = pt(i);
      final ctrl1 = Offset(p0.dx + (p1.dx - p0.dx) * 0.5, p0.dy);
      final ctrl2 = Offset(p0.dx + (p1.dx - p0.dx) * 0.5, p1.dy);
      linePath.cubicTo(ctrl1.dx, ctrl1.dy, ctrl2.dx, ctrl2.dy, p1.dx, p1.dy);
    }
    if (fullPoints < totalPoints - 1 && remainder > 0) {
      final p0 = pt(fullPoints);
      final p1 = pt(fullPoints + 1);
      final ctrl1 = Offset(p0.dx + (p1.dx - p0.dx) * 0.5, p0.dy);
      final ctrl2 = Offset(p0.dx + (p1.dx - p0.dx) * 0.5, p1.dy);
      final ex = p0.dx + (p1.dx - p0.dx) * remainder;
      final ey = _cubicY(p0.dy, ctrl1.dy, ctrl2.dy, p1.dy, remainder);
      linePath.cubicTo(
          p0.dx + (ctrl1.dx - p0.dx) * remainder,
          p0.dy + (ctrl1.dy - p0.dy) * remainder,
          ctrl1.dx + (ctrl2.dx - ctrl1.dx) * remainder,
          ctrl1.dy + (ctrl2.dy - ctrl1.dy) * remainder,
          ex,
          ey);
    }
    canvas.drawPath(linePath, linePaint);

    // Draw the glowing dot at the current head
    final headX = fullPoints < totalPoints - 1
        ? pt(fullPoints).dx +
            (pt(fullPoints + 1).dx - pt(fullPoints).dx) * remainder
        : pt(fullPoints).dx;
    final headY = fullPoints < totalPoints - 1
        ? _cubicY(
            pt(fullPoints).dy,
            pt(fullPoints).dy +
                (pt(fullPoints + 1).dy - pt(fullPoints).dy) * 0.0,
            pt(fullPoints + 1 < totalPoints ? fullPoints + 1 : fullPoints).dy,
            pt(fullPoints + 1 < totalPoints ? fullPoints + 1 : fullPoints).dy,
            remainder)
        : pt(fullPoints).dy;

    // Outer glow
    final glowPaint = Paint()
      ..color = grassGreen.withOpacity(0.25)
      ..style = PaintingStyle.fill;
    canvas.drawCircle(Offset(headX, headY), 14, glowPaint);
    // Inner dot
    final dotPaint = Paint()
      ..color = grassGreen
      ..style = PaintingStyle.fill;
    canvas.drawCircle(Offset(headX, headY), 7, dotPaint);
    // White center
    final whitePaint = Paint()
      ..color = Colors.white
      ..style = PaintingStyle.fill;
    canvas.drawCircle(Offset(headX, headY), 3, whitePaint);

    // Draw subtle horizontal grid lines
    final gridPaint = Paint()
      ..color = soilBrown.withOpacity(0.08)
      ..strokeWidth = 1;
    for (int i = 1; i <= 4; i++) {
      double y = size.height * i / 4;
      canvas.drawLine(Offset(0, y), Offset(size.width, y), gridPaint);
    }
  }

  double _cubicY(double p0, double p1, double p2, double p3, double t) {
    return (1 - t) * (1 - t) * (1 - t) * p0 +
        3 * (1 - t) * (1 - t) * t * p1 +
        3 * (1 - t) * t * t * p2 +
        t * t * t * p3;
  }

  @override
  bool shouldRepaint(_GrowthLinePainter old) => old.progress != progress;
}

// --- 4. HOW IT WORKS (Morphing & Connections) ---
class HowItWorksSection extends StatelessWidget {
  final ValueNotifier<double> relativeScrollNotifier;
  final double vh;
  final double stickyDuration;

  const HowItWorksSection(
      {super.key,
      required this.relativeScrollNotifier,
      required this.vh,
      required this.stickyDuration});

  @override
  Widget build(BuildContext context) {
    return RepaintBoundary(
        child: Container(
            color: Colors.transparent,
            padding: const EdgeInsets.symmetric(horizontal: 60),
            child: ValueListenableBuilder<double>(
                valueListenable: relativeScrollNotifier,
                builder: (context, relativeScroll, child) {
                  double enterProgress =
                      ((relativeScroll + vh) / vh).clamp(0.0, 1.0);
                  double progress = stickyDuration > 0
                      ? (relativeScroll / stickyDuration).clamp(0.0, 1.0)
                      : 0.0;

                  return Opacity(
                    opacity: enterProgress,
                    child: Row(
                      children: [
                        Expanded(
                            child:
                                Stack(alignment: Alignment.center, children: [
                          Transform.rotate(
                              angle: progress * math.pi,
                              child: Container(
                                width: 400,
                                height: 400,
                                decoration: BoxDecoration(
                                    shape: BoxShape.circle,
                                    border: Border.all(
                                        color: grassGreen.withOpacity(0.4),
                                        width: 2)),
                              )),
                          Transform.rotate(
                              angle: -progress * math.pi * 0.5,
                              child: Container(
                                width: 250,
                                height: 250,
                                decoration: BoxDecoration(
                                    shape: BoxShape.circle,
                                    border: Border.all(
                                        color: lightGreen.withOpacity(0.6),
                                        width: 4)),
                              )),
                          Transform.scale(
                              scale: 0.8 + (progress * 0.3),
                              child: Container(
                                padding: const EdgeInsets.all(40),
                                decoration: BoxDecoration(
                                    color: Colors.white.withOpacity(0.9),
                                    shape: BoxShape.circle,
                                    boxShadow: [
                                      BoxShadow(
                                          color: grassGreen.withOpacity(0.2),
                                          blurRadius: 40)
                                    ]),
                                child: const Icon(Icons.psychology_rounded,
                                    size: 100, color: grassGreen),
                              ))
                        ])),
                        Expanded(
                            child: ClipRRect(
                          borderRadius: BorderRadius.circular(40),
                          child: BackdropFilter(
                            filter: ui.ImageFilter.blur(sigmaX: 15, sigmaY: 15),
                            child: Container(
                              padding: const EdgeInsets.all(40),
                              decoration: BoxDecoration(
                                color: Colors.white
                                    .withOpacity(0.85), // Light glass
                                borderRadius: BorderRadius.circular(40),
                                boxShadow: [
                                  BoxShadow(
                                      color: Colors.black.withOpacity(0.1),
                                      blurRadius: 40)
                                ],
                                border: Border.all(
                                    color: Colors.white.withOpacity(0.8),
                                    width: 2),
                              ),
                              child: Column(
                                  mainAxisAlignment: MainAxisAlignment.center,
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    const Text('The Process',
                                        style: TextStyle(
                                          fontSize: 48,
                                          fontWeight: FontWeight.w900,
                                          color: darkSoil,
                                        )),
                                    const SizedBox(height: 80),
                                    _buildStep(
                                        1,
                                        'Input Your Data',
                                        'Select crop and location details.',
                                        Icons.edit_document,
                                        progress,
                                        0.0,
                                        0.33),
                                    _buildStep(
                                        2,
                                        'AI Analysis',
                                        'Our engine processes historical patterns.',
                                        Icons.memory,
                                        progress,
                                        0.33,
                                        0.66),
                                    _buildStep(
                                        3,
                                        'Get Predictions',
                                        'Receive actionable insights instantly.',
                                        Icons.insights,
                                        progress,
                                        0.66,
                                        1.0,
                                        isLast: true),
                                  ]),
                            ),
                          ),
                        ))
                      ],
                    ),
                  );
                })));
  }

  Widget _buildStep(int step, String title, String desc, IconData icon,
      double globalProgress, double start, double end,
      {bool isLast = false}) {
    double localProgress =
        ((globalProgress - start) / (end - start)).clamp(0.0, 1.0);
    double eased = Curves.easeOutBack.transform(localProgress);

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Column(
          children: [
            Transform.scale(
              scale: localProgress > 0 ? eased : 0.0,
              child: Container(
                width: 70,
                height: 70,
                decoration: BoxDecoration(
                  color: grassGreen,
                  shape: BoxShape.circle,
                  boxShadow: [
                    BoxShadow(
                        color: grassGreen.withOpacity(0.4),
                        blurRadius: 20,
                        offset: const Offset(0, 10))
                  ],
                ),
                child: Center(child: Icon(icon, color: Colors.white, size: 32)),
              ),
            ),
            if (!isLast)
              Container(
                width: 4,
                height: 80,
                margin: const EdgeInsets.symmetric(vertical: 12),
                decoration: BoxDecoration(
                    color:
                        soilBrown.withOpacity(0.2), // Reverted step line color
                    borderRadius: BorderRadius.circular(2)),
                alignment: Alignment.topCenter,
                child: FractionallySizedBox(
                  heightFactor: localProgress,
                  child: Container(
                      decoration: BoxDecoration(
                          color: grassGreen,
                          borderRadius: BorderRadius.circular(2))),
                ),
              ),
          ],
        ),
        const SizedBox(width: 40),
        Expanded(
          child: Opacity(
            opacity: localProgress,
            child: Transform.translate(
              offset: Offset(50 * (1 - eased), 0),
              child: Padding(
                padding: const EdgeInsets.only(top: 16.0, bottom: 24),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min, // PREVENT INFINITE HEIGHT
                  children: [
                    Text('STEP $step',
                        style: const TextStyle(
                          color: grassGreen,
                          fontWeight: FontWeight.bold,
                          fontSize: 16,
                          letterSpacing: 1.5,
                        )),
                    const SizedBox(height: 12),
                    Text(title,
                        style: const TextStyle(
                          fontSize: 28,
                          fontWeight: FontWeight.bold,
                          color: darkSoil,
                        )),
                    const SizedBox(height: 12),
                    Text(desc,
                        style: const TextStyle(
                          fontSize: 18,
                          color: soilBrown,
                          height: 1.5,
                        )),
                  ],
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }
}

// --- 5. FINAL CTA SECTION ---
class FinalCtaSection extends StatefulWidget {
  const FinalCtaSection({super.key});

  @override
  State<FinalCtaSection> createState() => _FinalCtaSectionState();
}

class _FinalCtaSectionState extends State<FinalCtaSection>
    with SingleTickerProviderStateMixin {
  late AnimationController _pulseController;

  @override
  void initState() {
    super.initState();
    _pulseController =
        AnimationController(vsync: this, duration: const Duration(seconds: 2))
          ..repeat(reverse: true);
  }

  @override
  void dispose() {
    _pulseController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(50),
      child: BackdropFilter(
        filter: ui.ImageFilter.blur(sigmaX: 20, sigmaY: 20),
        child: Container(
          margin: const EdgeInsets.symmetric(horizontal: 40),
          padding: const EdgeInsets.symmetric(vertical: 60, horizontal: 60),
          decoration: BoxDecoration(
            color: Colors.white.withOpacity(0.88),
            borderRadius: BorderRadius.circular(50),
            border: Border.all(color: Colors.white.withOpacity(0.9), width: 2),
            boxShadow: [
              BoxShadow(
                  color: Colors.black.withOpacity(0.06),
                  blurRadius: 60,
                  offset: const Offset(0, 20))
            ],
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              // Crop emoji row
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: ['🌾', '🌽', '🌿', '🌱', '🍅']
                    .map((e) => Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 8),
                          child: Text(e, style: const TextStyle(fontSize: 32)),
                        ))
                    .toList(),
              ),
              const SizedBox(height: 24),
              const Text(
                'Ready to Grow\nYour Profits?',
                textAlign: TextAlign.center,
                style: TextStyle(
                    fontSize: 56,
                    fontWeight: FontWeight.w900,
                    color: darkSoil,
                    letterSpacing: -2,
                    height: 1.1),
              ),
              const SizedBox(height: 16),
              const Text(
                'Join 10,000+ farmers using AI-powered price predictions to sell at the perfect time.',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 18, color: soilBrown, height: 1.6),
              ),
              const SizedBox(height: 48),
              AnimatedBuilder(
                animation: _pulseController,
                builder: (context, child) {
                  return MagneticHoverWidget(
                    child: Container(
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(50),
                        gradient: const LinearGradient(
                          colors: [Color(0xFF2E7D32), Color(0xFF66BB6A)],
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                        ),
                        boxShadow: [
                          BoxShadow(
                              color: grassGreen.withOpacity(
                                  (0.4 * _pulseController.value)
                                      .clamp(0.0, 1.0)),
                              blurRadius: 40 + (20 * _pulseController.value),
                              spreadRadius:
                                  (5 * _pulseController.value).clamp(0.0, 20.0))
                        ],
                      ),
                      child: ElevatedButton.icon(
                        onPressed: () {},
                        icon: const Icon(Icons.eco,
                            color: Colors.white, size: 24),
                        label: const Text('Start Predicting Free',
                            style: TextStyle(
                                fontSize: 22,
                                fontWeight: FontWeight.bold,
                                color: Colors.white)),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.transparent,
                          shadowColor: Colors.transparent,
                          padding: const EdgeInsets.symmetric(
                              horizontal: 60, vertical: 24),
                          shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(50)),
                          elevation: 0,
                        ),
                      ),
                    ),
                  );
                },
              ),
              const SizedBox(height: 28),
              const Text('No credit card required · Free forever plan',
                  style: TextStyle(fontSize: 14, color: soilBrown)),
            ],
          ),
        ),
      ),
    );
  }
}

// --- UTILITY WIDGETS ---
class FloatingParticles extends StatefulWidget {
  const FloatingParticles({super.key});

  @override
  State<FloatingParticles> createState() => _FloatingParticlesState();
}

class _FloatingParticlesState extends State<FloatingParticles>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller =
        AnimationController(vsync: this, duration: const Duration(seconds: 12))
          ..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, child) {
        return Stack(
          children: List.generate(14, (index) {
            double time = _controller.value * 2 * math.pi;
            double xOffset = math.sin(time + index * 0.7) * 90;
            double yOffset = math.cos(time * 0.8 + index * 1.3) * 70;
            // Alternate between leaf shades
            final leafColors = [
              const Color(0xFF388E3C),
              const Color(0xFF66BB6A),
              const Color(0xFF81C784),
              const Color(0xFF43A047),
            ];
            final color = leafColors[index % leafColors.length];
            return Positioned(
              left: (MediaQuery.of(context).size.width / 14) * index + xOffset,
              top: 80.0 + (index * 90) + yOffset,
              child: Opacity(
                  opacity: 0.35,
                  child: Transform.rotate(
                      angle: time * 0.5 + index,
                      child: Icon(Icons.eco, color: color, size: 44))),
            );
          }),
        );
      },
    );
  }
}

// --- LEAF TRAIL CURSOR EFFECT ---
class _LeafParticle {
  Offset position;
  double angle;
  double size;
  double opacity;
  double vy; // upward drift speed
  double vx; // horizontal drift
  final Color color;

  _LeafParticle({
    required this.position,
    required this.angle,
    required this.size,
    required this.color,
  })  : opacity = 1.0,
        vy = -(0.6 + math.Random().nextDouble() * 1.2),
        vx = (math.Random().nextDouble() - 0.5) * 1.5;
}

class LeafCursorOverlay extends StatefulWidget {
  final ValueNotifier<Offset> mouseNotifier;
  const LeafCursorOverlay({super.key, required this.mouseNotifier});

  @override
  State<LeafCursorOverlay> createState() => _LeafCursorOverlayState();
}

class _LeafCursorOverlayState extends State<LeafCursorOverlay>
    with SingleTickerProviderStateMixin {
  final List<_LeafParticle> _particles = [];
  late AnimationController _ticker;
  Offset _lastMousePos = Offset.zero;
  int _frameCount = 0;
  final _rng = math.Random();
  Size _screenSize = Size.zero;

  // Premium color palette
  final _leafColors = const [
    Color(0xFF2E7D32), // Deep Forest
    Color(0xFF388E3C), // Forest Green
    Color(0xFF43A047), // Rich Green
    Color(0xFF66BB6A), // Medium Light Green
    Color(0xFFA5D6A7), // Soft Mint
  ];

  @override
  void initState() {
    super.initState();
    _ticker =
        AnimationController(vsync: this, duration: const Duration(seconds: 1))
          ..repeat();
    _ticker.addListener(_tick);
    widget.mouseNotifier.addListener(_onMouseMove);
  }

  void _onMouseMove() {
    final raw = widget.mouseNotifier.value;
    if (_screenSize == Size.zero) return;
    final screenPos = Offset(
      (raw.dx + 0.5) * _screenSize.width,
      (raw.dy + 0.5) * _screenSize.height,
    );
    _lastMousePos = screenPos;
  }

  void _tick() {
    _frameCount++;

    // Spawn new leaves every 3 frames
    if (_frameCount % 3 == 0 && _lastMousePos != Offset.zero) {
      _particles.add(_LeafParticle(
        position: _lastMousePos +
            Offset(
                (_rng.nextDouble() - 0.5) * 10, (_rng.nextDouble() - 0.5) * 10),
        angle: _rng.nextDouble() * math.pi * 2,
        size: 8 + _rng.nextDouble() * 10,
        color: _leafColors[_rng.nextInt(_leafColors.length)],
      ));
    }

    // Animate particles
    for (final p in _particles) {
      p.position = Offset(p.position.dx + p.vx, p.position.dy + p.vy * 2);
      p.opacity -= 0.025;
      p.angle += 0.05;
    }
    _particles.removeWhere((p) => p.opacity <= 0);

    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    _ticker.removeListener(_tick);
    _ticker.dispose();
    widget.mouseNotifier.removeListener(_onMouseMove);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    _screenSize = MediaQuery.of(context).size;
    return Stack(
      children: [
        // Mini trailing leaves
        ..._particles.map((p) => Positioned(
              left: p.position.dx - p.size / 2,
              top: p.position.dy - p.size / 2,
              child: Opacity(
                opacity: p.opacity.clamp(0.0, 1.0),
                child: Transform.rotate(
                  angle: p.angle,
                  child: Icon(Icons.eco, color: p.color, size: p.size),
                ),
              ),
            )),

        // Main leaf cursor
        if (_lastMousePos != Offset.zero)
          Positioned(
            left: _lastMousePos.dx - 2, // Tip at (2,2) on 32x32 canvas
            top: _lastMousePos.dy - 2,
            child: SizedBox(
              width: 32,
              height: 32,
              child: CustomPaint(
                painter: _LeafCursorPainter(),
              ),
            ),
          ),
      ],
    );
  }
}

/// Draws a sleek leaf shape pointing upper-left, mimicking a standard cursor arrow.
/// The hotspot (click point) is at the tip — canvas position (2, 2).
class _LeafCursorPainter extends CustomPainter {
  const _LeafCursorPainter();

  @override
  void paint(Canvas canvas, Size size) {
    // ----------------------------------------------------------------
    // 1. BASE GEOMETRY (The perfect tilted teardrop)
    // ----------------------------------------------------------------
    final path = Path();
    path.moveTo(2, 2); // Hotspot
    // Right/Top edge
    path.quadraticBezierTo(
      size.width * 0.6,
      size.height * 0.05,
      size.width * 0.85,
      size.height * 0.45,
    );
    // Bottom bulb
    path.quadraticBezierTo(
      size.width * 0.95,
      size.height * 0.95,
      size.width * 0.45,
      size.height * 0.85,
    );
    // Left/Bottom edge
    path.quadraticBezierTo(
      size.width * 0.05,
      size.height * 0.6,
      2,
      2,
    );
    path.close();

    // ----------------------------------------------------------------
    // 2. 3D DROP SHADOW (Tighter, darker for a realistic float)
    // ----------------------------------------------------------------
    canvas.drawShadow(path, Colors.black87, 8.0, false);

    // ----------------------------------------------------------------
    // 3. BASE 3D GRADIENT (Dark edges, bright center)
    // ----------------------------------------------------------------
    final baseGradient = ui.Gradient.radial(
      Offset(size.width * 0.4, size.height * 0.4),
      size.width * 0.8,
      [
        const Color(0xFF69F0AE), // Bright neon mint in the center
        const Color(0xFF2E7D32), // Deep forest green
        const Color(0xFF1B5E20), // Almost black-green at the very edges
      ],
      [0.0, 0.6, 1.0],
    );

    final fillPaint = Paint()
      ..shader = baseGradient
      ..style = PaintingStyle.fill;
    canvas.drawPath(path, fillPaint);

    // ----------------------------------------------------------------
    // 4. EMBOSSED VEINS (Subtle dark lines with light highlights)
    // ----------------------------------------------------------------
    final veinPath = Path();
    // Main vein
    veinPath.moveTo(4, 4);
    veinPath.quadraticBezierTo(
      size.width * 0.45,
      size.height * 0.35,
      size.width * 0.7,
      size.height * 0.7,
    );

    // Draw dark indent (shadow of the vein)
    canvas.drawPath(
      veinPath,
      Paint()
        ..color = Colors.black.withOpacity(0.4)
        ..strokeWidth = 1.5
        ..style = PaintingStyle.stroke
        ..strokeCap = StrokeCap.round,
    );
    // Draw light catch (highlight of the vein, offset slightly)
    final veinHighlightPath = Path();
    veinHighlightPath.moveTo(5, 5);
    veinHighlightPath.quadraticBezierTo(
      size.width * 0.45 + 1,
      size.height * 0.35 + 1,
      size.width * 0.7 + 1,
      size.height * 0.7 + 1,
    );
    canvas.drawPath(
      veinHighlightPath,
      Paint()
        ..color = Colors.white.withOpacity(0.3)
        ..strokeWidth = 1.0
        ..style = PaintingStyle.stroke
        ..strokeCap = StrokeCap.round,
    );

    // ----------------------------------------------------------------
    // 5. SPECULAR HIGHLIGHT (The "Glassy/Epoxy" Reflection)
    // ----------------------------------------------------------------
    // This creates a bright, semi-transparent white curve across the top
    // left to make the leaf look shiny, wet, or encased in glass.
    final glossPath = Path();
    glossPath.moveTo(3, 3);
    glossPath.quadraticBezierTo(
      size.width * 0.5,
      size.height * 0.08,
      size.width * 0.75,
      size.height * 0.35,
    );
    glossPath.quadraticBezierTo(
      size.width * 0.4,
      size.height * 0.25,
      4,
      size.height * 0.35,
    );
    glossPath.close();

    final glossGradient = ui.Gradient.linear(
      const Offset(2, 2),
      Offset(size.width * 0.7, size.height * 0.4),
      [
        Colors.white.withOpacity(0.8), // Very bright at the tip
        Colors.white.withOpacity(0.0), // Fades to transparent
      ],
    );

    canvas.drawPath(
      glossPath,
      Paint()
        ..shader = glossGradient
        ..style = PaintingStyle.fill,
    );

    // ----------------------------------------------------------------
    // 6. CRISP BEVELED BORDER
    // ----------------------------------------------------------------
    // A crisp white stroke ensures it acts perfectly as a cursor over any background
    canvas.drawPath(
      path,
      Paint()
        ..color = Colors.white.withOpacity(0.9)
        ..strokeWidth = 1.5
        ..style = PaintingStyle.stroke
        ..strokeJoin = StrokeJoin.round,
    );
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class OrganicWaveClipper extends CustomClipper<Path> {
  @override
  Path getClip(Size size) {
    Path path = Path();
    path.lineTo(0, size.height - 120);
    path.quadraticBezierTo(
        size.width / 4, size.height, size.width / 2, size.height - 60);
    path.quadraticBezierTo(
        size.width * 0.75, size.height - 120, size.width, size.height - 30);
    path.lineTo(size.width, 0);
    path.close();
    return path;
  }

  @override
  bool shouldReclip(covariant CustomClipper<Path> oldClipper) => false;
}

class ScrollIndicator extends StatefulWidget {
  const ScrollIndicator({super.key});
  @override
  State<ScrollIndicator> createState() => _ScrollIndicatorState();
}

class _ScrollIndicatorState extends State<ScrollIndicator>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  @override
  void initState() {
    super.initState();
    _controller =
        AnimationController(vsync: this, duration: const Duration(seconds: 1))
          ..repeat(reverse: true);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, child) {
        return Transform.translate(
          offset: Offset(0, _controller.value * 20),
          child: const Column(
            mainAxisSize: MainAxisSize.min, // PREVENT INFINITE HEIGHT
            children: [
              Text('Scroll to explore',
                  style: TextStyle(
                      color: soilBrown,
                      fontWeight: FontWeight.bold,
                      fontSize: 16)),
              SizedBox(height: 12),
              Icon(Icons.keyboard_arrow_down, color: soilBrown, size: 30),
            ],
          ),
        );
      },
    );
  }
}

class HeroCtaButton extends StatefulWidget {
  final VoidCallback onTap;
  const HeroCtaButton({super.key, required this.onTap});
  @override
  State<HeroCtaButton> createState() => _HeroCtaButtonState();
}

class _HeroCtaButtonState extends State<HeroCtaButton> {
  bool _isHovered = false;
  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      onEnter: (_) => setState(() => _isHovered = true),
      onExit: (_) => setState(() => _isHovered = false),
      child: GestureDetector(
        onTap: widget.onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          padding: const EdgeInsets.symmetric(horizontal: 50, vertical: 22),
          decoration: BoxDecoration(
            color: _isHovered ? darkSoil : grassGreen,
            borderRadius: BorderRadius.circular(40),
            boxShadow: [
              BoxShadow(
                  color: (_isHovered ? darkSoil : grassGreen).withOpacity(0.5),
                  blurRadius: _isHovered ? 30 : 15,
                  offset: const Offset(0, 10))
            ],
          ),
          child: const Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('Get Started',
                  style: TextStyle(
                      color: Colors.white,
                      fontSize: 20,
                      fontWeight: FontWeight.bold)),
              SizedBox(width: 12),
              Icon(Icons.arrow_forward_rounded, color: Colors.white, size: 24),
            ],
          ),
        ),
      ),
    );
  }
}

class MagneticHoverWidget extends StatefulWidget {
  final Widget child;
  const MagneticHoverWidget({super.key, required this.child});
  @override
  State<MagneticHoverWidget> createState() => _MagneticHoverWidgetState();
}

class _MagneticHoverWidgetState extends State<MagneticHoverWidget> {
  double x = 0;
  double y = 0;
  bool isHovered = false;

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      onEnter: (_) => setState(() => isHovered = true),
      onExit: (_) => setState(() {
        isHovered = false;
        x = 0;
        y = 0;
      }),
      onHover: (details) {
        final RenderBox box = context.findRenderObject() as RenderBox;
        final centerX = box.size.width / 2;
        final centerY = box.size.height / 2;
        setState(() {
          x = (details.localPosition.dx - centerX) / centerX;
          y = (details.localPosition.dy - centerY) / centerY;
        });
      },
      child: TweenAnimationBuilder(
        tween: Tween<Offset>(
            begin: Offset.zero,
            end: isHovered ? Offset(x * 10, y * 10) : Offset.zero),
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeOutBack,
        builder: (context, Offset offset, child) {
          return Transform.translate(
            offset: offset,
            child: widget.child,
          );
        },
      ),
    );
  }
}

class HoverTiltWidget extends StatefulWidget {
  final Widget child;
  const HoverTiltWidget({super.key, required this.child});
  @override
  State<HoverTiltWidget> createState() => _HoverTiltWidgetState();
}

class _HoverTiltWidgetState extends State<HoverTiltWidget> {
  double x = 0;
  double y = 0;
  bool isHovered = false;

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      onEnter: (_) => setState(() => isHovered = true),
      onExit: (_) => setState(() {
        isHovered = false;
        x = 0;
        y = 0;
      }),
      onHover: (details) {
        final RenderBox box = context.findRenderObject() as RenderBox;
        final centerX = box.size.width / 2;
        final centerY = box.size.height / 2;
        setState(() {
          x = (details.localPosition.dx - centerX) / centerX;
          y = (details.localPosition.dy - centerY) / centerY;
        });
      },
      child: TweenAnimationBuilder(
        tween: Tween<Offset>(
            begin: Offset.zero, end: isHovered ? Offset(x, y) : Offset.zero),
        duration: const Duration(milliseconds: 400),
        curve: Curves.easeOutExpo,
        builder: (context, Offset offset, child) {
          return Transform(
            transform: Matrix4.identity()
              ..setEntry(3, 2, 0.001)
              ..rotateX(-offset.dy * 0.15)
              ..rotateY(offset.dx * 0.15),
            alignment: Alignment.center,
            child: widget.child,
          );
        },
      ),
    );
  }
}
