import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:audioplayers/audioplayers.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:speech_to_text/speech_to_text.dart';
import 'package:speech_to_text/speech_recognition_result.dart';
import 'package:wakelock_plus/wakelock_plus.dart';

import '../models/chat_message.dart';
import '../services/api_client.dart';
import '../services/camera_gaze_service.dart';
import '../widgets/eye_avatar.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final _messages = <ChatMessage>[];
  final _textController = TextEditingController();
  final _speakerIdController = TextEditingController(text: 'default-user');
  final _apiClient = ApiClient();
  final _gazeService = CameraGazeService();
  final _speech = SpeechToText();
  final _audioPlayer = AudioPlayer();

  bool _isLoading = false;
  bool _isRecording = false;
  bool _cameraReady = false;
  Offset _gaze = Offset.zero;
  bool _hasFace = false;
  String _emotion = 'neutral';

  @override
  void initState() {
    super.initState();
    _initCamera();
    _initSpeech();
    WakelockPlus.enable();
    _gazeService.gaze.addListener(_onGazeChanged);
    _gazeService.hasFace.addListener(_onFaceChanged);
    
    // Trigger greeting once everything is ready
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _sendGreeting();
      _startWakeWordListener();
    });
  }

  Future<void> _sendGreeting() async {
    // Send a hidden greeting to get Aliya's introduction
    try {
      final reply = await _apiClient.sendText(
        text: 'Привет, представься пожалуйста',
        language: 'ru',
        speakerId: _speakerIdController.text.trim(),
      );
      
      final audioUrl = reply.audioUrl == null
          ? null
          : _apiClient.resolveAudioUrl(reply.audioUrl!);

      if (mounted) {
        setState(() {
          _messages.add(
            ChatMessage(
              role: ChatRole.assistant,
              text: reply.assistantText,
              audioUrl: audioUrl,
              emotion: reply.emotion,
            ),
          );
          _emotion = reply.emotion;
        });
        
        if (audioUrl != null) {
          await _audioPlayer.play(UrlSource(audioUrl));
        }
      }
    } catch (e) {
      debugPrint('Greeting failed: $e');
    }
  }

  Future<void> _startWakeWordListener() async {
    bool available = await _speech.initialize();
    if (available) {
      _speech.listen(
        localeId: 'ru-RU',
        onResult: (result) {
          final words = result.recognizedWords.toLowerCase();
          if (words.contains('алия')) {
            // Wake word detected! 
            // We can either start recording or just act on the result if it contains a question
            debugPrint('Wake word "Алия" detected!');
            // If it's the final result and contains more than just the wake word, send it
            if (result.finalResult && words.length > 5) {
               _sendRecognizedText(result.recognizedWords);
            }
          }
        },
        listenOptions: SpeechListenOptions(
          cancelOnError: false,
          partialResults: true,
          listenMode: ListenMode.confirmation,
        ),
      );
    }
  }

  Future<void> _initSpeech() async {
    try {
      await _speech.initialize(
        onStatus: (status) => debugPrint('STT Status: $status'),
        onError: (error) => debugPrint('STT Error: $error'),
      );
    } catch (e) {
      debugPrint('Speech initialization failed: $e');
    }
  }

  Future<void> _initCamera() async {
    try {
      await _gazeService.initialize();
      if (mounted) {
        setState(() {
          _cameraReady = true;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _cameraReady = false;
        });
      }
    }
  }

  void _onGazeChanged() {
    if (!mounted) {
      return;
    }
    setState(() {
      _gaze = _gazeService.gaze.value;
    });
  }

  void _onFaceChanged() {
    if (!mounted) {
      return;
    }
    setState(() {
      _hasFace = _gazeService.hasFace.value;
    });
  }

  @override
  void dispose() {
    WakelockPlus.disable();
    _gazeService.gaze.removeListener(_onGazeChanged);
    _gazeService.hasFace.removeListener(_onFaceChanged);
    _gazeService.dispose();
    _apiClient.dispose();
    _audioPlayer.dispose();
    _textController.dispose();
    _speakerIdController.dispose();
    super.dispose();
  }

  List<Map<String, String>> _historyPayload() {
    final start = _messages.length > 8 ? _messages.length - 8 : 0;
    return _messages.sublist(start).map((message) {
      return {
        'role': message.role == ChatRole.user ? 'user' : 'assistant',
        'content': message.text,
      };
    }).toList();
  }

  Future<void> _sendText() async {
    final text = _textController.text.trim();
    if (text.isEmpty || _isLoading) {
      return;
    }

    setState(() {
      _messages.add(ChatMessage(role: ChatRole.user, text: text));
      _isLoading = true;
      _textController.clear();
    });

    try {
      final reply = await _apiClient.sendText(
        text: text,
        language: 'ru',
        speakerId: _speakerIdController.text.trim(),
        history: _historyPayload(),
      );

      final audioUrl = reply.audioUrl == null
          ? null
          : _apiClient.resolveAudioUrl(reply.audioUrl!);

      setState(() {
        _emotion = reply.emotion;
        _messages.add(
          ChatMessage(
            role: ChatRole.assistant,
            text: reply.assistantText,
            audioUrl: audioUrl,
            emotion: reply.emotion,
          ),
        );
      });

      if (audioUrl != null) {
        await _audioPlayer.play(UrlSource(audioUrl));
      }
    } catch (error) {
      setState(() {
        _messages.add(
          ChatMessage(
            role: ChatRole.assistant,
            text: 'Ошибка: $error',
            emotion: 'sad',
          ),
        );
        _emotion = 'sad';
      });
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _sendRecognizedText(String text) async {
    if (text.isEmpty || _isLoading) {
      return;
    }

    setState(() {
      _messages.add(ChatMessage(role: ChatRole.user, text: text));
      _isLoading = true;
    });

    try {
      final reply = await _apiClient.sendText(
        text: text,
        language: 'ru',
        speakerId: _speakerIdController.text.trim(),
        history: _historyPayload(),
      );

      final audioUrl = reply.audioUrl == null
          ? null
          : _apiClient.resolveAudioUrl(reply.audioUrl!);

      setState(() {
        _emotion = reply.emotion;
        _messages.add(
          ChatMessage(
            role: ChatRole.assistant,
            text: reply.assistantText,
            audioUrl: audioUrl,
            emotion: reply.emotion,
          ),
        );
      });

      if (audioUrl != null) {
        await _audioPlayer.play(UrlSource(audioUrl));
      }
    } catch (error) {
      setState(() {
        _messages.add(
          ChatMessage(
            role: ChatRole.assistant,
            text: 'Ошибка: $error',
            emotion: 'sad',
          ),
        );
        _emotion = 'sad';
      });
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _toggleRecording() async {
    if (_isLoading) {
      return;
    }

    if (_isRecording) {
      await _speech.stop();
      setState(() {
        _isRecording = false;
      });
      return;
    }

    final micPermission = await Permission.microphone.request();
    if (!mounted) return;
    if (!micPermission.isGranted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Разрешите доступ к микрофону')),
      );
      return;
    }

    bool speechAvailable = await _speech.initialize();
    if (!mounted) return;
    if (!speechAvailable) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Распознавание речи недоступно')),
      );
      return;
    }

    setState(() {
      _isRecording = true;
    });

    await _speech.listen(
      localeId: 'ru-RU',
      onResult: (SpeechRecognitionResult result) {
        setState(() {
          _textController.text = result.recognizedWords;
        });
        
        if (result.finalResult) {
          setState(() {
            _isRecording = false;
          });
          _sendRecognizedText(result.recognizedWords);
        }
      },
    );
  }


  @override
  Widget build(BuildContext context) {
    final cameraController = _gazeService.controller;

    return Scaffold(
      body: SafeArea(
        child: Container(
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              colors: [Color(0xFF000000), Color(0xFF0E0700), Color(0xFF000000)],
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
            ),
          ),
          child: Column(
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
                child: TextField(
                  controller: _speakerIdController,
                  style: const TextStyle(color: Color(0xFFFFBB73)),
                  decoration: InputDecoration(
                    labelText: 'Speaker ID',
                    hintText: 'например: user-1',
                    labelStyle: const TextStyle(color: Color(0xFFFF8A00)),
                    enabledBorder: OutlineInputBorder(
                      borderSide: BorderSide(color: Colors.orange.shade400),
                      borderRadius: BorderRadius.circular(14),
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderSide: const BorderSide(color: Color(0xFFFF8A00), width: 2),
                      borderRadius: BorderRadius.circular(14),
                    ),
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: AspectRatio(
                  aspectRatio: 16 / 9,
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(20),
                    child: Stack(
                      fit: StackFit.expand,
                      children: [
                        Container(color: Colors.black),
                        if (_cameraReady && cameraController != null)
                          Opacity(
                            opacity: 0.0,
                            child: CameraPreview(cameraController),
                          ),
                        Center(
                          child: EyeAvatar(
                            gaze: _gaze,
                            emotion: _emotion,
                            hasFace: _hasFace,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 12),
              Expanded(
                child: ListView.builder(
                  reverse: true,
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  itemCount: _messages.length,
                  itemBuilder: (context, index) {
                    final message = _messages[_messages.length - 1 - index];
                    final isUser = message.isUser;

                    return Align(
                      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
                      child: Container(
                        margin: const EdgeInsets.symmetric(vertical: 6),
                        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                        constraints: const BoxConstraints(maxWidth: 320),
                        decoration: BoxDecoration(
                          color: isUser ? const Color(0xFF2E1700) : const Color(0xFF151515),
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(
                            color: isUser
                                ? const Color(0xFFFF8A00)
                                : Colors.orange.shade200.withValues(alpha: 0.3),
                          ),
                        ),
                        child: Text(
                          message.text,
                          style: TextStyle(
                            color: isUser ? const Color(0xFFFFBB73) : Colors.white,
                            fontSize: 15,
                            height: 1.35,
                          ),
                        ),
                      ),
                    );
                  },
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(12, 4, 12, 12),
                child: Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: _textController,
                        style: const TextStyle(color: Colors.white),
                        decoration: InputDecoration(
                          hintText: 'Введите сообщение...',
                          hintStyle: TextStyle(color: Colors.white.withValues(alpha: 0.5)),
                          filled: true,
                          fillColor: const Color(0xFF111111),
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(14),
                            borderSide: const BorderSide(color: Color(0x44FF8A00)),
                          ),
                          enabledBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(14),
                            borderSide: const BorderSide(color: Color(0x44FF8A00)),
                          ),
                          focusedBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(14),
                            borderSide: const BorderSide(color: Color(0xAAFF8A00)),
                          ),
                        ),
                        onSubmitted: (_) => _sendText(),
                      ),
                    ),
                    const SizedBox(width: 8),
                    IconButton.filled(
                      onPressed: _isLoading ? null : _sendText,
                      icon: _isLoading
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Icon(Icons.send_rounded),
                    ),
                    const SizedBox(width: 6),
                    IconButton(
                      onPressed: _toggleRecording,
                      icon: Icon(
                        _isRecording ? Icons.stop_circle : Icons.mic,
                        color: _isRecording ? Colors.redAccent : const Color(0xFFFF8A00),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
