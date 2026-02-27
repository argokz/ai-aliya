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
  final _speakerIdController = TextEditingController(text: 'aliya');
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
  String? _partialTranscript; // For real-time feedback

  @override
  void initState() {
    super.initState();
    _initCamera();
    _initSpeech();
    WakelockPlus.enable();
    _gazeService.gaze.addListener(_onGazeChanged);
    _gazeService.hasFace.addListener(_onFaceChanged);
    
    // Trigger greeting once everything is ready
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      await Future.delayed(const Duration(milliseconds: 1000)); // Wait for UI to settle
      _sendGreeting();
      _startWakeWordListener();
    });
  }

  Future<void> _sendGreeting() async {
    // Send a hidden greeting to get Aliya's introduction
    try {
      final reply = await _apiClient.sendText(
        text: 'Алия, поздоровайся и коротко скажи, что ты готова помочь',
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
          debugPrint('Greeting Audio URL: $audioUrl');
          await _audioPlayer.play(UrlSource(audioUrl));
        }
      }
    } catch (e) {
      debugPrint('Greeting failed: $e');
    }
  }

  Future<void> _startWakeWordListener() async {
    if (_isRecording || _isLoading) return;

    bool available = await _speech.initialize(
      onStatus: (status) {
        debugPrint('STT Status: $status');
        if (status == 'done' || status == 'notListening') {
          // Restart listener if not manually recording or loading
          if (!_isRecording && !_isLoading && mounted) {
            _startWakeWordListener();
          }
        }
      },
      onError: (error) {
        debugPrint('STT Error: $error');
        // Retry after error
        if (mounted) {
           Future.delayed(const Duration(seconds: 2), _startWakeWordListener);
        }
      },
    );

    if (available && mounted) {
      _speech.listen(
        localeId: 'ru-RU',
        onResult: (result) {
          final words = result.recognizedWords.toLowerCase();
          
          setState(() {
            _partialTranscript = result.recognizedWords;
          });

          if (words.contains('алия')) {
            debugPrint('Wake word "Алия" detected in results: "$words"');
            
            if (result.finalResult) {
              _sendRecognizedText(result.recognizedWords);
              setState(() => _partialTranscript = null);
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
        onStatus: (status) => debugPrint('STT Init Status: $status'),
        onError: (error) => debugPrint('STT Init Error: $error'),
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

  Future<void> _processStreamingReply(String text) async {
    if (text.isEmpty || _isLoading) return;

    setState(() {
      _isLoading = true;
      _partialTranscript = null;
    });

    final assistantMsg = ChatMessage(
      role: ChatRole.assistant,
      text: '',
      emotion: 'neutral',
    );

    setState(() {
      _messages.add(assistantMsg);
    });

    final msgIndex = _messages.length - 1;
    String accumulatedText = '';

    try {
      final stream = _apiClient.sendStreamedChat(
        text: text,
        language: 'ru',
        speakerId: _speakerIdController.text.trim(),
        history: _historyPayload(),
      );

      await for (final event in stream) {
        if (!mounted) break;

        final type = event['type'] as String?;
        final content = event['content'];

        if (type == 'text' && content is String) {
          accumulatedText += content;
          // Filter out logical splitting character '|' and any stray <voice> tags for clean UI
          final displayText = accumulatedText
              .replaceAll('|', '')
              .replaceAll(RegExp(r'<voice>.*', dotAll: true), '')
              .trim();
          
          if (displayText != _messages[msgIndex].text) {
            setState(() {
              _messages[msgIndex] = _messages[msgIndex].copyWith(text: displayText);
            });
          }
        } else if (type == 'emotion' && content is String) {
          setState(() {
            _emotion = content;
            _messages[msgIndex] = _messages[msgIndex].copyWith(emotion: content);
          });
        } else if (type == 'audio' && content is String) {
          final audioUrl = _apiClient.resolveAudioUrl(content);
          debugPrint('Streamed Audio URL: $audioUrl');
          await _audioPlayer.play(UrlSource(audioUrl));
        } else if (type == 'error') {
          setState(() {
            _messages[msgIndex] = _messages[msgIndex].copyWith(
              text: 'Ошибка: $content',
              emotion: 'sad',
            );
            _emotion = 'sad';
          });
        }
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _messages[msgIndex] = _messages[msgIndex].copyWith(
            text: 'Ошибка связи: $e',
            emotion: 'sad',
          );
          _emotion = 'sad';
        });
      }
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _sendText() async {
    final text = _textController.text.trim();
    if (text.isEmpty || _isLoading) {
      return;
    }

    setState(() {
      _messages.add(ChatMessage(role: ChatRole.user, text: text));
      _textController.clear();
    });

    await _processStreamingReply(text);
  }

  Future<void> _sendRecognizedText(String text) async {
    if (text.isEmpty || _isLoading) {
      return;
    }

    setState(() {
      _messages.add(ChatMessage(role: ChatRole.user, text: text));
    });

    await _processStreamingReply(text);
  }

  Future<void> _toggleRecording() async {
    if (_isLoading) {
      return;
    }

    if (_isRecording) {
      await _speech.stop();
      setState(() {
        _isRecording = false;
        _partialTranscript = null;
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
          _partialTranscript = result.recognizedWords;
          _textController.text = result.recognizedWords;
        });
        
        if (result.finalResult) {
          setState(() {
            _isRecording = false;
            _partialTranscript = null;
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
                    hintText: 'например: aliya',
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
                        if (!_isLoading && !_isRecording)
                          Positioned(
                            bottom: 10,
                            right: 15,
                            child: Text(
                              'Алия слушает...',
                              style: TextStyle(
                                color: const Color(0xFFFF8A00).withValues(alpha: 0.6),
                                fontSize: 11,
                                fontWeight: FontWeight.bold,
                                letterSpacing: 0.5,
                              ),
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
                  itemCount: _messages.length + (_partialTranscript != null ? 1 : 0),
                  itemBuilder: (context, index) {
                    if (_partialTranscript != null && index == 0) {
                      // Show partial results at the bottom
                      return Align(
                        alignment: Alignment.centerRight,
                        child: Container(
                          margin: const EdgeInsets.symmetric(vertical: 6),
                          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                          decoration: BoxDecoration(
                            color: const Color(0xFF2E1700).withValues(alpha: 0.5),
                            borderRadius: BorderRadius.circular(16),
                            border: Border.all(color: const Color(0xFFFF8A00).withValues(alpha: 0.5)),
                          ),
                          child: Text(
                            _partialTranscript!,
                            style: const TextStyle(color: Color(0xFFFFBB73), fontStyle: FontStyle.italic),
                          ),
                        ),
                      );
                    }

                    final messageIndex = _partialTranscript != null ? index - 1 : index;
                    if (messageIndex < 0 || messageIndex >= _messages.length) return const SizedBox();
                    
                    final message = _messages[_messages.length - 1 - messageIndex];
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
                              child: CircularProgressIndicator(strokeWidth: 2, color: Colors.orange),
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
