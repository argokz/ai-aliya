enum ChatRole { user, assistant }

class ChatMessage {
  const ChatMessage({
    required this.role,
    required this.text,
    this.audioUrl,
    this.emotion,
  });

  final ChatRole role;
  final String text;
  final String? audioUrl;
  final String? emotion;

  bool get isUser => role == ChatRole.user;
}
