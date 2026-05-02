import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:livestock_app/api/auth_api.dart';
import 'package:livestock_app/main.dart';

void main() {
  testWidgets('login screen renders', (tester) async {
    await tester.pumpWidget(const LivestockApp());

    expect(find.text('تسجيل الدخول'), findsOneWidget);
    expect(find.text('اسم المستخدم'), findsOneWidget);
    expect(find.text('كلمة المرور'), findsOneWidget);
    expect(find.text('إنشاء حساب جديد'), findsOneWidget);
  });

  testWidgets('register screen opens', (tester) async {
    await tester.pumpWidget(const LivestockApp());

    await tester.tap(find.text('إنشاء حساب جديد'));
    await tester.pumpAndSettle();

    expect(find.text('تسجيل حساب جديد'), findsWidgets);
    expect(find.text('اسم المنشأة'), findsOneWidget);
  });

  testWidgets('home screen renders current user and farm', (tester) async {
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
  });
}
