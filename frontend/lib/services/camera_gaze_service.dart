import 'dart:async';
import 'dart:ui';

import 'package:camera/camera.dart';
import 'package:flutter/foundation.dart';
import 'package:google_mlkit_face_detection/google_mlkit_face_detection.dart';
import 'package:permission_handler/permission_handler.dart';

class CameraGazeService {
  final ValueNotifier<Offset> gaze = ValueNotifier(Offset.zero);
  final ValueNotifier<bool> hasFace = ValueNotifier(false);

  CameraController? _controller;
  FaceDetector? _faceDetector;
  bool _isProcessing = false;
  int _frameCounter = 0;

  CameraController? get controller => _controller;

  Future<void> initialize() async {
    final cameraPermission = await Permission.camera.request();
    if (!cameraPermission.isGranted) {
      throw Exception('Camera permission denied');
    }

    final cameras = await availableCameras();
    if (cameras.isEmpty) {
      throw Exception('No cameras available');
    }

    final selected = cameras.firstWhere(
      (c) => c.lensDirection == CameraLensDirection.front,
      orElse: () => cameras.first,
    );

    _controller = CameraController(
      selected,
      ResolutionPreset.medium,
      enableAudio: false,
      imageFormatGroup: ImageFormatGroup.nv21,
    );

    await _controller!.initialize();

    _faceDetector = FaceDetector(
      options: FaceDetectorOptions(
        enableClassification: false,
        enableContours: false,
        performanceMode: FaceDetectorMode.fast,
      ),
    );

    await _controller!.startImageStream(_processFrame);
  }

  Future<void> _processFrame(CameraImage image) async {
    if (_isProcessing) {
      return;
    }

    _frameCounter += 1;
    if (_frameCounter % 3 != 0) {
      return;
    }

    final controller = _controller;
    final detector = _faceDetector;
    if (controller == null || detector == null) {
      return;
    }

    final inputImage = _toInputImage(image, controller.description.sensorOrientation);
    if (inputImage == null) {
      return;
    }

    _isProcessing = true;
    try {
      final faces = await detector.processImage(inputImage);
      if (faces.isEmpty) {
        hasFace.value = false;
        return;
      }

      hasFace.value = true;
      final face = faces.first;

      final centerX = (face.boundingBox.left + face.boundingBox.right) / 2;
      final centerY = (face.boundingBox.top + face.boundingBox.bottom) / 2;

      final normalizedX = ((centerX / image.width) - 0.5) * -2.0;
      final normalizedY = ((centerY / image.height) - 0.5) * 2.0;

      gaze.value = Offset(
        normalizedX.clamp(-1.0, 1.0),
        normalizedY.clamp(-1.0, 1.0),
      );
    } finally {
      _isProcessing = false;
    }
  }

  InputImage? _toInputImage(CameraImage image, int sensorRotation) {
    final rotation = InputImageRotationValue.fromRawValue(sensorRotation);
    if (rotation == null) {
      return null;
    }

    final format = InputImageFormatValue.fromRawValue(image.format.raw);
    if (format == null) {
      return null;
    }

    final bytes = _concatenatePlanes(image.planes);

    return InputImage.fromBytes(
      bytes: bytes,
      metadata: InputImageMetadata(
        size: Size(image.width.toDouble(), image.height.toDouble()),
        rotation: rotation,
        format: format,
        bytesPerRow: image.planes.first.bytesPerRow,
      ),
    );
  }

  Uint8List _concatenatePlanes(List<Plane> planes) {
    final allBytes = <int>[];
    for (final plane in planes) {
      allBytes.addAll(plane.bytes);
    }
    return Uint8List.fromList(allBytes);
  }

  Future<void> dispose() async {
    await _controller?.stopImageStream();
    await _controller?.dispose();
    await _faceDetector?.close();
    gaze.dispose();
    hasFace.dispose();
  }
}
