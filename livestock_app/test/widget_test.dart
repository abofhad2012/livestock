import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:livestock_app/api/auth_api.dart';
import 'package:livestock_app/main.dart';

void main() {
  const auth = AuthResponse(
    ok: true,
    token: 'test-token',
    user: <String, dynamic>{
      'id': 1,
      'username': 'owner1',
      'full_name': 'مالك التجربة',
    },
    farm: <String, dynamic>{
      'id': 1,
      'name': 'منشأة التجربة',
    },
  );

  testWidgets('login screen renders', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: LoginPage(),
      ),
    );

    expect(find.text('تسجيل الدخول'), findsOneWidget);
    expect(find.text('اسم المستخدم'), findsOneWidget);
    expect(find.text('كلمة المرور'), findsOneWidget);
    expect(find.text('إنشاء حساب جديد'), findsOneWidget);
  });

  testWidgets('register screen opens', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: LoginPage(),
      ),
    );

    await tester.tap(find.text('إنشاء حساب جديد'));
    await tester.pumpAndSettle();

    expect(find.text('تسجيل حساب جديد'), findsWidgets);
    expect(find.text('اسم المنشأة'), findsOneWidget);
  });

  testWidgets('home screen renders current user and farm', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: HomePage(auth: auth),
      ),
    );

    expect(find.text('الرئيسية'), findsOneWidget);
    expect(find.text('مالك التجربة'), findsOneWidget);
    expect(find.text('منشأة التجربة'), findsOneWidget);
    expect(find.text('المخزون'), findsOneWidget);
    expect(find.text('شراء'), findsOneWidget);
    expect(find.text('بيع'), findsOneWidget);
    expect(find.text('خروج'), findsOneWidget);
  });

  testWidgets('stock content renders current farm and quantities', (tester) async {
    const stockData = StockResponse(
      ok: true,
      farm: <String, dynamic>{
        'id': 1,
        'name': 'منشأة المخزون',
      },
      items: <StockItem>[
        StockItem(
          kind: 'SHEEP',
          kindLabel: 'غنم',
          livestockClass: 'NONE',
          classLabel: '?',
          quantity: '7.00',
        ),
      ],
      byKind: <StockKindSummary>[
        StockKindSummary(
          kind: 'SHEEP',
          kindLabel: 'غنم',
          total: '7.00',
          classes: <StockClassQuantity>[
            StockClassQuantity(
              livestockClass: 'NONE',
              classLabel: '?',
              quantity: '7.00',
            ),
          ],
        ),
      ],
    );

    await tester.pumpWidget(
      const MaterialApp(
        home: Directionality(
          textDirection: TextDirection.rtl,
          child: StockContent(stock: stockData),
        ),
      ),
    );

    expect(find.text('المخزون'), findsOneWidget);
    expect(find.text('منشأة المخزون'), findsOneWidget);
    expect(find.text('غنم'), findsOneWidget);
    expect(find.text('الإجمالي: 7.00'), findsOneWidget);
  });

  testWidgets('purchase screen opens from home', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: HomePage(auth: auth),
      ),
    );

    await tester.tap(find.text('شراء'));
    await tester.pumpAndSettle();

    expect(find.text('تسجيل شراء'), findsWidgets);
    expect(find.text('نوع المواشي'), findsOneWidget);
    expect(find.text('الكمية'), findsOneWidget);
    expect(find.text('سعر الوحدة'), findsOneWidget);
  });

  testWidgets('sale screen opens from home', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: HomePage(auth: auth),
      ),
    );

    await tester.tap(find.text('بيع'));
    await tester.pumpAndSettle();

    expect(find.text('تسجيل بيع'), findsWidgets);
    expect(find.text('نوع المواشي'), findsOneWidget);
    expect(find.text('الكمية'), findsOneWidget);
    expect(find.text('سعر الوحدة'), findsOneWidget);
  });
}
