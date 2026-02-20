import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import 'screens/chat_screen.dart';

class AliaApp extends StatelessWidget {
  const AliaApp({super.key});

  @override
  Widget build(BuildContext context) {
    const seed = Color(0xFFFF8A00);

    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Alia Assistant',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: seed,
          brightness: Brightness.dark,
        ),
        scaffoldBackgroundColor: const Color(0xFF030303),
        textTheme: GoogleFonts.exo2TextTheme(ThemeData.dark().textTheme),
        useMaterial3: true,
      ),
      home: const ChatScreen(),
    );
  }
}
