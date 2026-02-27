import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';

class EyeAvatar extends StatefulWidget {
  const EyeAvatar({
    super.key,
    required this.gaze,
    required this.emotion,
    required this.hasFace,
  });

  final Offset gaze;
  final String emotion;
  final bool hasFace;

  @override
  State<EyeAvatar> createState() => _EyeAvatarState();
}

class _EyeAvatarState extends State<EyeAvatar> with SingleTickerProviderStateMixin {
  late final AnimationController _blinkController;
  Timer? _blinkTimer;
  final _random = Random();

  @override
  void initState() {
    super.initState();
    _blinkController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 130),
      lowerBound: 0,
      upperBound: 1,
    );
    _scheduleBlink();
  }

  void _scheduleBlink() {
    _blinkTimer?.cancel();
    final wait = Duration(milliseconds: 1800 + _random.nextInt(1600));
    _blinkTimer = Timer(wait, () async {
      if (!mounted) {
        return;
      }
      await _blinkController.forward();
      await _blinkController.reverse();
      _scheduleBlink();
    });
  }

  @override
  void dispose() {
    _blinkTimer?.cancel();
    _blinkController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _blinkController,
      builder: (context, _) {
        return CustomPaint(
          size: const Size(320, 170),
          painter: _EyePainter(
            gaze: widget.gaze,
            blink: _blinkController.value,
            emotion: widget.emotion,
            hasFace: widget.hasFace,
          ),
        );
      },
    );
  }
}

class _EyePainter extends CustomPainter {
  _EyePainter({
    required this.gaze,
    required this.blink,
    required this.emotion,
    required this.hasFace,
  });

  final Offset gaze;
  final double blink;
  final String emotion;
  final bool hasFace;

  @override
  void paint(Canvas canvas, Size size) {
    final centerY = size.height / 2;
    final leftCenter = Offset(size.width * 0.32, centerY);
    final rightCenter = Offset(size.width * 0.68, centerY);

    final openFactor = (1.0 - blink).clamp(0.08, 1.0);
    final eyeHeight = switch (emotion) {
      'surprised' => 92.0 * openFactor,
      'happy' => 70.0 * openFactor,
      'sad' => 64.0 * openFactor,
      _ => 78.0 * openFactor,
    };

    _drawEye(canvas, leftCenter, eyeHeight);
    _drawEye(canvas, rightCenter, eyeHeight);

    final labelStyle = TextStyle(
      color: Colors.orange.shade300.withValues(alpha: hasFace ? 0.9 : 0.55),
      fontSize: 14,
      letterSpacing: 1.2,
      fontWeight: FontWeight.w600,
    );
    final textPainter = TextPainter(
      text: TextSpan(text: hasFace ? emotion.toUpperCase() : 'SEARCHING FACE', style: labelStyle),
      textDirection: TextDirection.ltr,
    )..layout();

    textPainter.paint(
      canvas,
      Offset((size.width - textPainter.width) / 2, size.height - 28),
    );
  }

  void _drawEye(Canvas canvas, Offset center, double eyeHeight) {
    // Draw the eye shell
    const eyeWidth = 118.0; // Increased width
    final eyeRect = Rect.fromCenter(center: center, width: eyeWidth, height: eyeHeight);
    final eyeRRect = RRect.fromRectAndRadius(eyeRect, const Radius.circular(46)); // Softer curve

    final shellPaint = Paint()
      ..shader = LinearGradient(
        colors: [
          Colors.orange.shade100.withValues(alpha: 0.98),
          Colors.orange.shade50.withValues(alpha: 0.9),
        ],
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
      ).createShader(eyeRect);

    canvas.drawRRect(eyeRRect, shellPaint);

    // Pupil ranges
    const pupilRangeX = 24.0; // wider range
    final pupilRangeY = max(8.0, eyeHeight * 0.2);

    final emotionX = switch (emotion) {
      'thinking' => -6.0,
      'surprised' => 4.0,
      'happy' => 2.0,
      _ => 0.0,
    };

    final pupilCenter = Offset(
      center.dx + (gaze.dx * pupilRangeX) + emotionX,
      center.dy + (gaze.dy * pupilRangeY),
    );

    // SMARTER BROWN EYES
    // 1. Outer Iris (Brown)
    final irisPaint = Paint()..color = const Color(0xFF5D4037); // Deep Hazel/Brown
    canvas.drawCircle(pupilCenter, 28, irisPaint);

    // 2. Iris Texture/Ring
    final ringPaint = Paint()
      ..color = const Color(0xFF795548).withValues(alpha: 0.6)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3;
    canvas.drawCircle(pupilCenter, 20, ringPaint);

    // 3. Pupil (Black)
    final pupilPaint = Paint()..color = const Color(0xFF1B0F00);
    canvas.drawCircle(pupilCenter, 12, pupilPaint);

    // 4. Primary Glare
    final glarePaint = Paint()..color = Colors.white.withValues(alpha: 0.88);
    canvas.drawCircle(pupilCenter.translate(-7, -8), 5, glarePaint);
    
    // 5. Secondary "Smart" Glare
    final smallGlarePaint = Paint()..color = Colors.white.withValues(alpha: 0.4);
    canvas.drawCircle(pupilCenter.translate(9, 6), 2, smallGlarePaint);

    if (emotion == 'sad' || emotion == 'empathetic') {
      final eyelidPaint = Paint()
        ..color = const Color(0x992B1600)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 4;
      final path = Path()
        ..moveTo(eyeRect.left + 8, eyeRect.top + 12)
        ..quadraticBezierTo(
          eyeRect.center.dx,
          eyeRect.top + 4,
          eyeRect.right - 8,
          eyeRect.top + 16,
        );
      canvas.drawPath(path, eyelidPaint);
    }
  }

  @override
  bool shouldRepaint(covariant _EyePainter oldDelegate) {
    return oldDelegate.gaze != gaze ||
        oldDelegate.blink != blink ||
        oldDelegate.emotion != emotion ||
        oldDelegate.hasFace != hasFace;
  }
}
