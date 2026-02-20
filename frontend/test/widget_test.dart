import 'package:flutter_test/flutter_test.dart';

import 'package:ai_aliya_frontend/models/chat_message.dart';

void main() {
  test('ChatMessage reports user role correctly', () {
    const userMessage = ChatMessage(role: ChatRole.user, text: 'hello');
    const assistantMessage = ChatMessage(role: ChatRole.assistant, text: 'hi');

    expect(userMessage.isUser, isTrue);
    expect(assistantMessage.isUser, isFalse);
  });
}
