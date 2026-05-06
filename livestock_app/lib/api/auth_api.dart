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

  Future<StockResponse> stock({required String token}) async {
    final response = await http.get(
      _uri('/api/stock/'),
      headers: <String, String>{
        'Accept': 'application/json',
        'Authorization': 'Token $token',
      },
    );

    final decoded = _decodeJson(response);

    if (response.statusCode == 200 && decoded['ok'] == true) {
      return StockResponse.fromJson(decoded);
    }

    throw AuthApiException(
      _errorMessage(decoded, fallback: 'Stock request failed'),
      statusCode: response.statusCode,
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

    final decoded = _decodeJson(response);

    if ((response.statusCode == 200 || response.statusCode == 201) &&
        decoded['ok'] == true) {
      return AuthResponse.fromJson(decoded);
    }

    throw AuthApiException(
      _errorMessage(decoded, fallback: 'Request failed'),
      statusCode: response.statusCode,
    );
  }

  Map<String, dynamic> _decodeJson(http.Response response) {
    final decoded = jsonDecode(utf8.decode(response.bodyBytes));

    if (decoded is! Map<String, dynamic>) {
      throw AuthApiException(
        'Invalid server response',
        statusCode: response.statusCode,
      );
    }

    return decoded;
  }

  String _errorMessage(
    Map<String, dynamic> decoded, {
    required String fallback,
  }) {
    final rawError = decoded['error'] ?? decoded['detail'] ?? decoded['errors'];

    if (rawError is List) {
      return rawError.join('\n');
    }

    return rawError?.toString() ?? fallback;
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

class StockResponse {
  const StockResponse({
    required this.ok,
    required this.farm,
    required this.items,
    required this.byKind,
  });

  final bool ok;
  final Map<String, dynamic>? farm;
  final List<StockItem> items;
  final List<StockKindSummary> byKind;

  String get farmName {
    return (farm?['name'] ?? '').toString();
  }

  bool get isEmpty {
    return items.isEmpty && byKind.isEmpty;
  }

  factory StockResponse.fromJson(Map<String, dynamic> json) {
    final rawFarm = json['farm'];
    final rawItems = json['items'];
    final rawByKind = json['by_kind'];

    return StockResponse(
      ok: json['ok'] == true,
      farm: rawFarm is Map ? Map<String, dynamic>.from(rawFarm) : null,
      items: rawItems is List
          ? rawItems
              .map((item) => StockItem.fromJson(Map<String, dynamic>.from(item as Map)))
              .toList()
          : const <StockItem>[],
      byKind: rawByKind is List
          ? rawByKind
              .map(
                (item) => StockKindSummary.fromJson(
                  Map<String, dynamic>.from(item as Map),
                ),
              )
              .toList()
          : const <StockKindSummary>[],
    );
  }
}

class StockItem {
  const StockItem({
    required this.kind,
    required this.kindLabel,
    required this.livestockClass,
    required this.classLabel,
    required this.quantity,
  });

  final String kind;
  final String kindLabel;
  final String livestockClass;
  final String classLabel;
  final String quantity;

  factory StockItem.fromJson(Map<String, dynamic> json) {
    return StockItem(
      kind: (json['kind'] ?? '').toString(),
      kindLabel: (json['kind_label'] ?? '').toString(),
      livestockClass: (json['livestock_class'] ?? '').toString(),
      classLabel: (json['class_label'] ?? '').toString(),
      quantity: (json['quantity'] ?? '0.00').toString(),
    );
  }
}

class StockKindSummary {
  const StockKindSummary({
    required this.kind,
    required this.kindLabel,
    required this.total,
    required this.classes,
  });

  final String kind;
  final String kindLabel;
  final String total;
  final List<StockClassQuantity> classes;

  factory StockKindSummary.fromJson(Map<String, dynamic> json) {
    final rawClasses = json['classes'];

    return StockKindSummary(
      kind: (json['kind'] ?? '').toString(),
      kindLabel: (json['kind_label'] ?? '').toString(),
      total: (json['total'] ?? '0.00').toString(),
      classes: rawClasses is List
          ? rawClasses
              .map(
                (item) => StockClassQuantity.fromJson(
                  Map<String, dynamic>.from(item as Map),
                ),
              )
              .toList()
          : const <StockClassQuantity>[],
    );
  }
}

class StockClassQuantity {
  const StockClassQuantity({
    required this.livestockClass,
    required this.classLabel,
    required this.quantity,
  });

  final String livestockClass;
  final String classLabel;
  final String quantity;

  factory StockClassQuantity.fromJson(Map<String, dynamic> json) {
    return StockClassQuantity(
      livestockClass: (json['livestock_class'] ?? '').toString(),
      classLabel: (json['class_label'] ?? '').toString(),
      quantity: (json['quantity'] ?? '0.00').toString(),
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
