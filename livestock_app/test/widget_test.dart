import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
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

    final registerPageScrollable = find.descendant(
      of: find.byType(RegisterPage),
      matching: find.byWidgetPredicate(
        (widget) =>
            widget is Scrollable &&
            widget.axisDirection == AxisDirection.down,
      ),
    );
    expect(registerPageScrollable, findsOneWidget);

    final registerButton = find.widgetWithText(
      FilledButton,
      'إنشاء الحساب',
    );

    await tester.scrollUntilVisible(
      registerButton,
      200,
      scrollable: registerPageScrollable,
    );

    expect(registerButton, findsOneWidget);
  });
}
