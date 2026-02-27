import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

class AssistantReply {
  const AssistantReply({
    required this.userText,
    required this.assistantText,
    required this.emotion,
    this.audioUrl,
  });

  final String userText;
  final String assistantText;
  final String emotion;
  final String? audioUrl;

  factory AssistantReply.fromJson(Map<String, dynamic> json) {
    return AssistantReply(
      userText: json['user_text'] as String? ?? '',
      assistantText: json['assistant_text'] as String? ?? '',
      emotion: json['emotion'] as String? ?? 'neutral',
      audioUrl: json['audio_url'] as String?,
    );
  }
}

class ApiClient {
  ApiClient({http.Client? client, String? baseUrl})
      : _client = client ?? http.Client(),
        _baseUrl =
            baseUrl ?? const String.fromEnvironment('API_BASE_URL', defaultValue: 'https://itwin.kz/api-aliya/api/v1');

  final http.Client _client;
  final String _baseUrl;

  Future<AssistantReply> sendText({
    required String text,
    required String language,
    String? speakerId,
    bool generateAudio = true,
    List<Map<String, String>> history = const [],
  }) async {
    final response = await _client.post(
      Uri.parse('$_baseUrl/assistant/chat'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'text': text,
        'language': language,
        'speaker_id': speakerId,
        'generate_audio': generateAudio,
        'history': history,
      }),
    );

    if (response.statusCode >= 400) {
      throw Exception(_extractError(response.body));
    }

    return AssistantReply.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Stream<Map<String, dynamic>> sendStreamedChat({
    required String text,
    required String language,
    String? speakerId,
    bool generateAudio = true,
    List<Map<String, String>> history = const [],
  }) async* {
    final request = http.Request(
      'POST',
      Uri.parse('$_baseUrl/assistant/chat-stream'),
    );
    request.headers['Content-Type'] = 'application/json';
    request.body = jsonEncode({
      'text': text,
      'language': language,
      'speaker_id': speakerId,
      'generate_audio': generateAudio,
      'history': history,
    });

    final streamedResponse = await _client.send(request);

    if (streamedResponse.statusCode >= 400) {
        final body = await streamedResponse.stream.bytesToString();
        throw Exception(_extractError(body));
    }

    final stream = streamedResponse.stream
        .transform(utf8.decoder)
        .transform(const LineSplitter());

    await for (final line in stream) {
      if (line.trim().isEmpty) continue;
      try {
        yield jsonDecode(line) as Map<String, dynamic>;
      } catch (e) {
        print('Error decoding stream line: $e');
      }
    }
  }

  Future<AssistantReply> sendAudio({
    required File audioFile,
    required String language,
    String? speakerId,
    bool generateAudio = true,
    List<Map<String, String>> history = const [],
  }) async {
    final request = http.MultipartRequest(
      'POST',
      Uri.parse('$_baseUrl/assistant/transcribe-and-chat'),
    );

    request.fields['language'] = language;
    request.fields['generate_audio'] = generateAudio.toString();
    request.fields['history_json'] = jsonEncode(history);
    if (speakerId != null && speakerId.isNotEmpty) {
      request.fields['speaker_id'] = speakerId;
    }

    request.files.add(
      await http.MultipartFile.fromPath('audio', audioFile.path),
    );

    final streamed = await _client.send(request);
    final response = await http.Response.fromStream(streamed);

    if (response.statusCode >= 400) {
      throw Exception(_extractError(response.body));
    }

    return AssistantReply.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  String resolveAudioUrl(String relativeOrAbsolute) {
    if (relativeOrAbsolute.startsWith('http://') ||
        relativeOrAbsolute.startsWith('https://')) {
      return relativeOrAbsolute;
    }

    final apiRoot = _baseUrl.replaceAll(RegExp(r'/api/v1$'), '');
    return '$apiRoot$relativeOrAbsolute';
  }

  String _extractError(String body) {
    try {
      final payload = jsonDecode(body) as Map<String, dynamic>;
      final detail = payload['detail'];
      if (detail is String) {
        return detail;
      }
    } catch (_) {
      // ignore parse errors
    }
    return 'Request failed';
  }

  void dispose() {
    _client.close();
  }
}
