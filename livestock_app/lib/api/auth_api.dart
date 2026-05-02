import 'dart:convert';

import 'package:http/http.dart' as http;

class AuthApi {
  const AuthApi();

  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://127.0.0.1:8000',
  );

  Uri _uri(String path) {
    final root = baseUrl.replaceAll(RegExp(r'/+$'), '');
    return Uri.parse('$root$path');
  }

  Future<AuthResponse> login({
    required String username,
    required String password,
  }) {
    return _postAuth(
      '/api/auth/login/',
      <String, String>{
        'username': username,
        'password': password,
      },
    );
  }

  Future<AuthResponse> register({
    required String username,
    required String password,
    required String fullName,
    required String phone,
    required String farmName,
  }) {
    return _postAuth(
      '/api/auth/register/',
      <String, String>{
        'username': username,
        'password': password,
        'full_name': fullName,
        'phone': phone,
        'farm_name': farmName,
      },
    );
  }

  Future<AuthResponse> _postAuth(
    String path,
    Map<String, String> payload,
  ) async {
    final response = await http.post(
      _uri(path),
      headers: const <String, String>{
        'Content-Type': 'application/json; charset=UTF-8',
      },
      body: jsonEncode(payload),
    );

    final decoded = jsonDecode(utf8.decode(response.bodyBytes));

    if (decoded is! Map<String, dynamic>) {
      throw AuthApiException(
        'Invalid server response',
        statusCode: response.statusCode,
      );
    }

    if ((response.statusCode == 200 || response.statusCode == 201) &&
        decoded['ok'] == true) {
      return AuthResponse.fromJson(decoded);
    }

    final rawError = decoded['error'] ?? decoded['detail'] ?? decoded['errors'];
    final message = rawError is List
        ? rawError.join('\n')
        : (rawError?.toString() ?? 'Request failed');

    throw AuthApiException(message, statusCode: response.statusCode);
  }
}

class AuthResponse {
  const AuthResponse({
    required this.ok,
    required this.token,
    required this.user,
    required this.farm,
  });

  final bool ok;
  final String token;
  final Map<String, dynamic> user;
  final Map<String, dynamic>? farm;

  factory AuthResponse.fromJson(Map<String, dynamic> json) {
    return AuthResponse(
      ok: json['ok'] == true,
      token: (json['token'] ?? '').toString(),
      user: Map<String, dynamic>.from(json['user'] as Map),
      farm: json['farm'] == null
          ? null
          : Map<String, dynamic>.from(json['farm'] as Map),
    );
  }
}

class AuthApiException implements Exception {
  const AuthApiException(this.message, {this.statusCode});

  final String message;
  final int? statusCode;

  @override
  String toString() {
    if (statusCode == null) {
      return message;
    }
    return '$message ($statusCode)';
  }
}
