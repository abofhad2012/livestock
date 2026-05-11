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

  Future<PurchaseResponse> purchase({
    required String token,
    required String kind,
    required String livestockClass,
    required String quantity,
    required String unitPrice,
    required String idempotencyKey,
  }) async {
    final response = await http.post(
      _uri('/api/purchase/'),
      headers: <String, String>{
        'Content-Type': 'application/json; charset=UTF-8',
        'Authorization': 'Token $token',
      },
      body: jsonEncode(<String, String>{
        'kind': kind,
        'livestock_class': livestockClass,
        'quantity': quantity,
        'unit_price': unitPrice,
        'idempotency_key': idempotencyKey,
      }),
    );

    final decoded = _decodeJson(response);

    if ((response.statusCode == 200 || response.statusCode == 201) &&
        decoded['ok'] == true) {
      return PurchaseResponse.fromJson(decoded);
    }

    throw AuthApiException(
      _errorMessage(decoded, fallback: 'Purchase request failed'),
      statusCode: response.statusCode,
    );
  }

  Future<PurchaseResponse> sale({
    required String token,
    required String kind,
    required String livestockClass,
    required String quantity,
    required String unitPrice,
    required String idempotencyKey,
  }) async {
    final response = await http.post(
      _uri('/api/sale/'),
      headers: <String, String>{
        'Content-Type': 'application/json; charset=UTF-8',
        'Authorization': 'Token $token',
      },
      body: jsonEncode(<String, String>{
        'kind': kind,
        'livestock_class': livestockClass,
        'quantity': quantity,
        'unit_price': unitPrice,
        'idempotency_key': idempotencyKey,
      }),
    );

    final decoded = _decodeJson(response);

    if ((response.statusCode == 200 || response.statusCode == 201) &&
        decoded['ok'] == true) {
      return PurchaseResponse.fromJson(decoded);
    }

    throw AuthApiException(
      _errorMessage(decoded, fallback: 'Sale request failed'),
      statusCode: response.statusCode,
    );
  }

  Future<AuthResponse> me({required String token}) async {
    final response = await http.get(
      _uri('/api/auth/me/'),
      headers: <String, String>{
        'Accept': 'application/json',
        'Authorization': 'Token $token',
      },
    );

    final decoded = _decodeJson(response);

    if (response.statusCode == 200 && decoded['ok'] == true) {
      final current = AuthResponse.fromJson(decoded);
      return AuthResponse(
        ok: current.ok,
        token: token,
        user: current.user,
        farm: current.farm,
      );
    }

    throw AuthApiException(
      _errorMessage(decoded, fallback: 'Session restore failed'),
      statusCode: response.statusCode,
    );
  }

  Future<void> logout({required String token}) async {
    if (token.isEmpty) {
      return;
    }

    final response = await http.post(
      _uri('/api/auth/logout/'),
      headers: <String, String>{
        'Accept': 'application/json',
        'Authorization': 'Token $token',
      },
    );

    final decoded = _decodeJson(response);

    if (response.statusCode == 200 && decoded['ok'] == true) {
      return;
    }

    throw AuthApiException(
      _errorMessage(decoded, fallback: 'Logout failed'),
      statusCode: response.statusCode,
    );
  }

  Future<ReportsSummaryResponse> reportsSummary({
    required String token,
  }) async {
    final response = await http.get(
      _uri('/api/reports/summary/'),
      headers: <String, String>{
        'Accept': 'application/json',
        'Authorization': 'Token $token',
      },
    );

    final decoded = _decodeJson(response);

    if (response.statusCode == 200 && decoded['ok'] == true) {
      return ReportsSummaryResponse.fromJson(decoded);
    }

    throw AuthApiException(
      _errorMessage(decoded, fallback: 'Reports summary request failed'),
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

class PurchaseResponse {
  const PurchaseResponse({
    required this.ok,
    required this.transaction,
    required this.line,
    required this.idempotent,
  });

  final bool ok;
  final PurchaseTransaction transaction;
  final PurchaseLine line;
  final bool idempotent;

  factory PurchaseResponse.fromJson(Map<String, dynamic> json) {
    return PurchaseResponse(
      ok: json['ok'] == true,
      transaction: PurchaseTransaction.fromJson(
        Map<String, dynamic>.from(json['transaction'] as Map),
      ),
      line: json['line'] == null
          ? PurchaseLine.empty()
          : PurchaseLine.fromJson(
              Map<String, dynamic>.from(json['line'] as Map),
            ),
      idempotent: json['idempotent'] == true,
    );
  }
}

class PurchaseTransaction {
  const PurchaseTransaction({
    required this.id,
    required this.reference,
    required this.date,
    required this.totalAmount,
    required this.amountPaid,
    required this.amountDue,
  });

  final int id;
  final String reference;
  final String date;
  final String totalAmount;
  final String amountPaid;
  final String amountDue;

  factory PurchaseTransaction.fromJson(Map<String, dynamic> json) {
    return PurchaseTransaction(
      id: int.tryParse((json['id'] ?? '0').toString()) ?? 0,
      reference: (json['reference'] ?? '').toString(),
      date: (json['date'] ?? '').toString(),
      totalAmount: (json['total_amount'] ?? '0.00').toString(),
      amountPaid: (json['amount_paid'] ?? '0.00').toString(),
      amountDue: (json['amount_due'] ?? '0.00').toString(),
    );
  }
}

class PurchaseLine {
  const PurchaseLine({
    required this.kind,
    required this.livestockClass,
    required this.quantity,
    required this.unitPrice,
    required this.amount,
  });

  final String kind;
  final String livestockClass;
  final String quantity;
  final String unitPrice;
  final String amount;

  factory PurchaseLine.fromJson(Map<String, dynamic> json) {
    return PurchaseLine(
      kind: (json['kind'] ?? '').toString(),
      livestockClass: (json['livestock_class'] ?? '').toString(),
      quantity: (json['quantity'] ?? '0.00').toString(),
      unitPrice: (json['unit_price'] ?? '0.00').toString(),
      amount: (json['amount'] ?? '0.00').toString(),
    );
  }

  factory PurchaseLine.empty() {
    return const PurchaseLine(
      kind: '',
      livestockClass: '',
      quantity: '0.00',
      unitPrice: '0.00',
      amount: '0.00',
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

class ReportsSummaryResponse {
  const ReportsSummaryResponse({
    required this.ok,
    required this.farm,
    required this.period,
    required this.totals,
    required this.recentTransactions,
  });

  final bool ok;
  final Map<String, dynamic>? farm;
  final ReportPeriod period;
  final ReportTotals totals;
  final List<ReportRecentTransaction> recentTransactions;

  String get farmName {
    return (farm?['name'] ?? '').toString();
  }

  factory ReportsSummaryResponse.fromJson(Map<String, dynamic> json) {
    final rawFarm = json['farm'];
    final rawRecentTransactions = json['recent_transactions'];

    return ReportsSummaryResponse(
      ok: json['ok'] == true,
      farm: rawFarm is Map ? Map<String, dynamic>.from(rawFarm) : null,
      period: ReportPeriod.fromJson(
        Map<String, dynamic>.from(json['period'] as Map),
      ),
      totals: ReportTotals.fromJson(
        Map<String, dynamic>.from(json['totals'] as Map),
      ),
      recentTransactions: rawRecentTransactions is List
          ? rawRecentTransactions
              .map(
                (item) => ReportRecentTransaction.fromJson(
                  Map<String, dynamic>.from(item as Map),
                ),
              )
              .toList()
          : const <ReportRecentTransaction>[],
    );
  }
}

class ReportPeriod {
  const ReportPeriod({
    required this.from,
    required this.to,
  });

  final String from;
  final String to;

  factory ReportPeriod.fromJson(Map<String, dynamic> json) {
    return ReportPeriod(
      from: (json['from'] ?? '').toString(),
      to: (json['to'] ?? '').toString(),
    );
  }
}

class ReportTotals {
  const ReportTotals({
    required this.currentStockQuantity,
    required this.purchasesCount,
    required this.salesCount,
    required this.purchasesTotal,
    required this.salesTotal,
    required this.netSalesMinusPurchases,
  });

  final String currentStockQuantity;
  final int purchasesCount;
  final int salesCount;
  final String purchasesTotal;
  final String salesTotal;
  final String netSalesMinusPurchases;

  factory ReportTotals.fromJson(Map<String, dynamic> json) {
    return ReportTotals(
      currentStockQuantity: (json['current_stock_quantity'] ?? '0.00').toString(),
      purchasesCount: int.tryParse((json['purchases_count'] ?? '0').toString()) ?? 0,
      salesCount: int.tryParse((json['sales_count'] ?? '0').toString()) ?? 0,
      purchasesTotal: (json['purchases_total'] ?? '0.00').toString(),
      salesTotal: (json['sales_total'] ?? '0.00').toString(),
      netSalesMinusPurchases:
          (json['net_sales_minus_purchases'] ?? '0.00').toString(),
    );
  }
}

class ReportRecentTransaction {
  const ReportRecentTransaction({
    required this.id,
    required this.reference,
    required this.date,
    required this.txType,
    required this.txTypeLabel,
    required this.totalAmount,
    required this.amountPaid,
    required this.amountDue,
  });

  final int id;
  final String reference;
  final String date;
  final String txType;
  final String txTypeLabel;
  final String totalAmount;
  final String amountPaid;
  final String amountDue;

  factory ReportRecentTransaction.fromJson(Map<String, dynamic> json) {
    return ReportRecentTransaction(
      id: int.tryParse((json['id'] ?? '0').toString()) ?? 0,
      reference: (json['reference'] ?? '').toString(),
      date: (json['date'] ?? '').toString(),
      txType: (json['tx_type'] ?? '').toString(),
      txTypeLabel: (json['tx_type_label'] ?? '').toString(),
      totalAmount: (json['total_amount'] ?? '0.00').toString(),
      amountPaid: (json['amount_paid'] ?? '0.00').toString(),
      amountDue: (json['amount_due'] ?? '0.00').toString(),
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
