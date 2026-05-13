import 'package:flutter/material.dart';

import 'api/auth_api.dart';
import 'auth/token_store.dart';
import 'theme/app_theme.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const LivestockApp());
}

class LivestockApp extends StatelessWidget {
  const LivestockApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'محاسبة المواشي',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.dark,
      home: const AuthGate(),
    );
  }
}

void openHome(BuildContext context, AuthResponse auth) {
  Navigator.pushAndRemoveUntil<void>(
    context,
    MaterialPageRoute<void>(
      builder: (_) => HomePage(auth: auth),
    ),
    (Route<dynamic> route) => false,
  );
}

class AuthGate extends StatefulWidget {
  const AuthGate({super.key});

  @override
  State<AuthGate> createState() => _AuthGateState();
}

class _AuthGateState extends State<AuthGate> {
  final _api = const AuthApi();
  final _tokenStore = const TokenStore();

  late Future<AuthResponse?> _sessionFuture;

  @override
  void initState() {
    super.initState();
    _sessionFuture = _restoreSession();
  }

  Future<AuthResponse?> _restoreSession() async {
    final token = await _tokenStore.readToken();
    if (token == null || token.isEmpty) {
      return null;
    }

    try {
      return await _api.me(token: token);
    } catch (_) {
      await _tokenStore.clearToken();
      return null;
    }
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<AuthResponse?>(
      future: _sessionFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Directionality(
            textDirection: TextDirection.rtl,
            child: Scaffold(
              body: Center(child: CircularProgressIndicator()),
            ),
          );
        }

        final auth = snapshot.data;
        if (auth == null) {
          return const LoginPage();
        }

        return HomePage(auth: auth);
      },
    );
  }
}

class SiteBrandHeader extends StatelessWidget {
  const SiteBrandHeader({
    super.key,
    required this.title,
    required this.subtitle,
  });

  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: <Widget>[
        Container(
          width: 72,
          height: 72,
          decoration: BoxDecoration(
            color: AppTheme.surfaceAlt,
            borderRadius: BorderRadius.circular(24),
            border: Border.all(color: AppTheme.border),
            boxShadow: <BoxShadow>[
              BoxShadow(
                color: AppTheme.primary.withValues(alpha: 0.18),
                blurRadius: 28,
                offset: const Offset(0, 12),
              ),
            ],
          ),
          child: const Center(
            child: Text(
              '🐑',
              style: TextStyle(fontSize: 34),
            ),
          ),
        ),
        const SizedBox(height: 22),
        Text(
          title,
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                fontSize: 30,
                color: AppTheme.primary,
                fontWeight: FontWeight.w900,
              ),
        ),
        const SizedBox(height: 10),
        Text(
          subtitle,
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: AppTheme.muted,
                height: 1.7,
              ),
        ),
      ],
    );
  }
}

class AuthPanel extends StatelessWidget {
  const AuthPanel({
    super.key,
    required this.children,
  });

  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Directionality(
      textDirection: TextDirection.rtl,
      child: Scaffold(
        body: SafeArea(
          child: DecoratedBox(
            decoration: const BoxDecoration(
              gradient: RadialGradient(
                center: Alignment.topCenter,
                radius: 1.3,
                colors: <Color>[
                  Color(0xFF0F2D47),
                  AppTheme.background,
                ],
              ),
            ),
            child: Center(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(22),
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 520),
                  child: Card(
                    child: Padding(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 26,
                        vertical: 34,
                      ),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: children,
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class LoginPage extends StatefulWidget {
  const LoginPage({super.key});

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final _api = const AuthApi();
  final _tokenStore = const TokenStore();
  final _formKey = GlobalKey<FormState>();

  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();

  bool _isLoading = false;
  String? _errorMessage;

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  String? _required(String? value, String message) {
    if (value == null || value.trim().isEmpty) {
      return message;
    }
    return null;
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final response = await _api.login(
        username: _usernameController.text.trim(),
        password: _passwordController.text,
      );

      await _tokenStore.saveToken(response.token);

      if (!mounted) {
        return;
      }

      Navigator.of(context).pushReplacement(
        MaterialPageRoute<void>(
          builder: (_) => HomePage(auth: response),
        ),
      );
    } on AuthApiException catch (error) {
      if (!mounted) {
        return;
      }

      setState(() {
        _errorMessage = 'خطأ: ${error.message}';
      });
    } catch (error) {
      if (!mounted) {
        return;
      }

      setState(() {
        _errorMessage = 'خطأ: $error';
      });
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  void _openRegister() {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => const RegisterPage(),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return AuthPanel(
      children: <Widget>[
        const SiteBrandHeader(
          title: 'محاسبة المواشي',
          subtitle: 'إدارة عمليات الشراء والبيع والتقارير الخاصة بمنشأتك.',
        ),
        const SizedBox(height: 30),
        Text(
          'تسجيل الدخول',
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                fontSize: 28,
                color: AppTheme.primary,
              ),
        ),
        const SizedBox(height: 26),
        Form(
          key: _formKey,
          child: Column(
            children: <Widget>[
              TextFormField(
                controller: _usernameController,
                textInputAction: TextInputAction.next,
                decoration: const InputDecoration(
                  labelText: 'اسم المستخدم',
                ),
                validator: (value) => _required(
                  value,
                  'اكتب اسم المستخدم',
                ),
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _passwordController,
                obscureText: true,
                decoration: const InputDecoration(
                  labelText: 'كلمة المرور',
                ),
                validator: (value) => _required(
                  value,
                  'اكتب كلمة المرور',
                ),
                onFieldSubmitted: (_) => _submit(),
              ),
              const SizedBox(height: 22),
              FilledButton(
                onPressed: _isLoading ? null : _submit,
                child: _isLoading
                    ? const SizedBox(
                        width: 22,
                        height: 22,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('دخول'),
              ),
            ],
          ),
        ),
        if (_errorMessage != null) ...[
          const SizedBox(height: 20),
          ErrorCard(message: _errorMessage!),
        ],
        const SizedBox(height: 22),
        TextButton(
          onPressed: _isLoading ? null : _openRegister,
          child: const Text('إنشاء حساب جديد'),
        ),
      ],
    );
  }
}

class RegisterPage extends StatefulWidget {
  const RegisterPage({super.key});

  @override
  State<RegisterPage> createState() => _RegisterPageState();
}

class _RegisterPageState extends State<RegisterPage> {
  final _api = const AuthApi();
  final _tokenStore = const TokenStore();
  final _formKey = GlobalKey<FormState>();

  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  final _fullNameController = TextEditingController();
  final _phoneController = TextEditingController();
  final _farmNameController = TextEditingController();

  bool _isLoading = false;
  String? _errorMessage;

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    _fullNameController.dispose();
    _phoneController.dispose();
    _farmNameController.dispose();
    super.dispose();
  }

  String? _required(String? value, String message) {
    if (value == null || value.trim().isEmpty) {
      return message;
    }
    return null;
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final response = await _api.register(
        username: _usernameController.text.trim(),
        password: _passwordController.text,
        fullName: _fullNameController.text.trim(),
        phone: _phoneController.text.trim(),
        farmName: _farmNameController.text.trim(),
      );

      await _tokenStore.saveToken(response.token);

      if (!mounted) {
        return;
      }

      Navigator.of(context).pushAndRemoveUntil(
        MaterialPageRoute<void>(
          builder: (_) => HomePage(auth: response),
        ),
        (Route<dynamic> route) => false,
      );
    } on AuthApiException catch (error) {
      if (!mounted) {
        return;
      }

      setState(() {
        _errorMessage = 'خطأ: ${error.message}';
      });
    } catch (error) {
      if (!mounted) {
        return;
      }

      setState(() {
        _errorMessage = 'خطأ: $error';
      });
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return AuthPanel(
      children: <Widget>[
        const SiteBrandHeader(
          title: 'محاسبة المواشي',
          subtitle: 'أنشئ حسابك واربطه بمنشأة مستقلة لإدارة العمليات والتقارير.',
        ),
        const SizedBox(height: 30),
        Text(
          'تسجيل حساب جديد',
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                fontSize: 26,
                color: AppTheme.primary,
              ),
        ),
        const SizedBox(height: 24),
        Form(
          key: _formKey,
          child: Column(
            children: <Widget>[
              TextFormField(
                controller: _usernameController,
                textInputAction: TextInputAction.next,
                decoration: const InputDecoration(
                  labelText: 'اسم المستخدم',
                ),
                validator: (value) => _required(
                  value,
                  'اكتب اسم المستخدم',
                ),
              ),
              const SizedBox(height: 14),
              TextFormField(
                controller: _passwordController,
                obscureText: true,
                textInputAction: TextInputAction.next,
                decoration: const InputDecoration(
                  labelText: 'كلمة المرور',
                ),
                validator: (value) => _required(
                  value,
                  'اكتب كلمة المرور',
                ),
              ),
              const SizedBox(height: 14),
              TextFormField(
                controller: _fullNameController,
                textInputAction: TextInputAction.next,
                decoration: const InputDecoration(
                  labelText: 'الاسم الكامل',
                ),
                validator: (value) => _required(
                  value,
                  'اكتب الاسم الكامل',
                ),
              ),
              const SizedBox(height: 14),
              TextFormField(
                controller: _phoneController,
                textInputAction: TextInputAction.next,
                decoration: const InputDecoration(
                  labelText: 'رقم الجوال',
                ),
              ),
              const SizedBox(height: 14),
              TextFormField(
                controller: _farmNameController,
                decoration: const InputDecoration(
                  labelText: 'اسم المنشأة',
                ),
                validator: (value) => _required(
                  value,
                  'اكتب اسم المنشأة',
                ),
                onFieldSubmitted: (_) => _submit(),
              ),
              const SizedBox(height: 22),
              FilledButton(
                onPressed: _isLoading ? null : _submit,
                child: _isLoading
                    ? const SizedBox(
                        width: 22,
                        height: 22,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('إنشاء الحساب'),
              ),
            ],
          ),
        ),
        if (_errorMessage != null) ...[
          const SizedBox(height: 20),
          ErrorCard(message: _errorMessage!),
        ],
      ],
    );
  }
}

class HomePage extends StatelessWidget {
  const HomePage({
    super.key,
    required this.auth,
  });

  final AuthResponse auth;

  String get _fullName {
    return (auth.user['full_name'] ?? auth.user['username'] ?? '').toString();
  }

  String get _farmName {
    return (auth.farm?['name'] ?? '').toString();
  }

  void _openStock(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => StockPage(auth: auth),
      ),
    );
  }

  void _openPurchase(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => PurchasePage(auth: auth),
      ),
    );
  }

  void _openSale(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => SalePage(auth: auth),
      ),
    );
  }

  void _openReports(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => ReportsPage(auth: auth),
      ),
    );
  }

  Future<void> _logout(BuildContext context) async {
    final token = auth.token;
    final tokenStore = const TokenStore();
    final api = const AuthApi();

    try {
      await api.logout(token: token);
    } catch (_) {
      // Local logout still matters even if the server token was already gone.
    } finally {
      await tokenStore.clearToken();
    }

    if (!context.mounted) {
      return;
    }

    Navigator.pushAndRemoveUntil<void>(
      context,
      MaterialPageRoute<void>(
        builder: (_) => const LoginPage(),
      ),
      (Route<dynamic> route) => false,
    );
  }

  @override
  Widget build(BuildContext context) {
    final actions = <HomeDashboardAction>[
      HomeDashboardAction(
        title: 'المخزون',
        subtitle: 'عرض الكميات الحالية حسب النوع',
        icon: Icons.inventory_2_outlined,
        onPressed: () => _openStock(context),
      ),
      HomeDashboardAction(
        title: 'شراء',
        subtitle: 'تسجيل مشتريات جديدة للمزرعة',
        icon: Icons.add_shopping_cart,
        onPressed: () => _openPurchase(context),
      ),
      HomeDashboardAction(
        title: 'بيع',
        subtitle: 'تسجيل بيع مع خصم المخزون',
        icon: Icons.point_of_sale,
        onPressed: () => _openSale(context),
      ),
      HomeDashboardAction(
        title: 'التقارير',
        subtitle: 'ملخص المشتريات والمبيعات وآخر العمليات',
        icon: Icons.analytics_outlined,
        onPressed: () => _openReports(context),
      ),
    ];

    return Directionality(
      textDirection: TextDirection.rtl,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('الرئيسية'),
          actions: <Widget>[
            TextButton.icon(
              onPressed: () => _logout(context),
              icon: const Icon(Icons.logout),
              label: const Text('خروج'),
            ),
          ],
        ),
        body: SafeArea(
          child: DecoratedBox(
            decoration: const BoxDecoration(
              gradient: RadialGradient(
                center: Alignment.topCenter,
                radius: 1.25,
                colors: <Color>[
                  Color(0xFF0F2D47),
                  AppTheme.background,
                ],
              ),
            ),
            child: ListView(
              padding: const EdgeInsets.all(22),
              children: <Widget>[
                Center(
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 900),
                    child: Column(
                      children: <Widget>[
                        Card(
                          child: Padding(
                            padding: const EdgeInsets.all(22),
                            child: Column(
                              children: <Widget>[
                                Container(
                                  width: 62,
                                  height: 62,
                                  decoration: BoxDecoration(
                                    color: AppTheme.surfaceAlt,
                                    borderRadius: BorderRadius.circular(22),
                                    border: Border.all(color: AppTheme.border),
                                  ),
                                  child: const Center(
                                    child: Text(
                                      '🐑',
                                      style: TextStyle(fontSize: 30),
                                    ),
                                  ),
                                ),
                                const SizedBox(height: 16),
                                Text(
                                  'محاسبة المواشي',
                                  textAlign: TextAlign.center,
                                  style: Theme.of(context)
                                      .textTheme
                                      .headlineSmall
                                      ?.copyWith(
                                        color: AppTheme.primary,
                                        fontWeight: FontWeight.w900,
                                      ),
                                ),
                                const SizedBox(height: 8),
                                Text(
                                  _fullName,
                                  textAlign: TextAlign.center,
                                  style: Theme.of(context).textTheme.titleLarge,
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  _farmName,
                                  textAlign: TextAlign.center,
                                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                                        color: AppTheme.muted,
                                      ),
                                ),
                              ],
                            ),
                          ),
                        ),
                        const SizedBox(height: 18),
                        GridView.builder(
                          shrinkWrap: true,
                          physics: const NeverScrollableScrollPhysics(),
                          gridDelegate:
                              const SliverGridDelegateWithMaxCrossAxisExtent(
                            maxCrossAxisExtent: 260,
                            mainAxisSpacing: 14,
                            crossAxisSpacing: 14,
                            mainAxisExtent: 148,
                          ),
                          itemCount: actions.length,
                          itemBuilder: (context, index) {
                            return HomeDashboardCard(action: actions[index]);
                          },
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class HomeDashboardAction {
  const HomeDashboardAction({
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.onPressed,
  });

  final String title;
  final String subtitle;
  final IconData icon;
  final VoidCallback onPressed;
}

class HomeDashboardCard extends StatelessWidget {
  const HomeDashboardCard({
    super.key,
    required this.action,
  });

  final HomeDashboardAction action;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(22),
        onTap: action.onPressed,
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Icon(
                action.icon,
                color: AppTheme.primary,
                size: 32,
              ),
              const Spacer(),
              Text(
                action.title,
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                      color: AppTheme.text,
                      fontWeight: FontWeight.w900,
                    ),
              ),
              const SizedBox(height: 6),
              Text(
                action.subtitle,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: AppTheme.muted,
                      height: 1.35,
                    ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class ReportsPage extends StatefulWidget {
  const ReportsPage({
    super.key,
    required this.auth,
  });

  final AuthResponse auth;

  @override
  State<ReportsPage> createState() => _ReportsPageState();
}

class _ReportsPageState extends State<ReportsPage> {
  final _api = const AuthApi();

  late Future<ReportsSummaryResponse> _summaryFuture;

  @override
  void initState() {
    super.initState();
    _summaryFuture = _loadSummary();
  }

  Future<ReportsSummaryResponse> _loadSummary() {
    return _api.reportsSummary(token: widget.auth.token);
  }

  void _refresh() {
    setState(() {
      _summaryFuture = _loadSummary();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Directionality(
      textDirection: TextDirection.rtl,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('التقارير'),
          actions: <Widget>[
            IconButton(
              onPressed: _refresh,
              icon: const Icon(Icons.refresh),
              tooltip: 'تحديث',
            ),
          ],
        ),
        body: SafeArea(
          child: FutureBuilder<ReportsSummaryResponse>(
            future: _summaryFuture,
            builder: (context, snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return const Center(child: CircularProgressIndicator());
              }

              if (snapshot.hasError) {
                final error = snapshot.error;
                final message = error is AuthApiException
                    ? error.message
                    : error.toString();

                return Padding(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: <Widget>[
                      ErrorCard(message: 'خطأ: $message'),
                      const SizedBox(height: 16),
                      FilledButton(
                        onPressed: _refresh,
                        child: const Text('إعادة المحاولة'),
                      ),
                    ],
                  ),
                );
              }

              final summary = snapshot.data;
              if (summary == null) {
                return const Center(
                  child: Text('لا توجد بيانات تقارير.'),
                );
              }

              return ReportsContent(
                summary: summary,
              );
            },
          ),
        ),
      ),
    );
  }
}

class ReportsContent extends StatelessWidget {
  const ReportsContent({
    super.key,
    required this.summary,
  });

  final ReportsSummaryResponse summary;

  @override
  Widget build(BuildContext context) {
    final totals = summary.totals;

    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 760),
        child: ListView(
          padding: const EdgeInsets.all(24),
          children: <Widget>[
            Text(
              'التقارير',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 8),
            Text(
              summary.farmName,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 4),
            Text(
              '${summary.period.from} - ${summary.period.to}',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const SizedBox(height: 24),
            ReportMetricCard(
              title: 'المخزون الحالي',
              value: totals.currentStockQuantity,
              subtitle: 'إجمالي الكمية',
            ),
            const SizedBox(height: 12),
            ReportMetricCard(
              title: 'إجمالي المشتريات',
              value: totals.purchasesTotal,
              subtitle: 'العدد: ${totals.purchasesCount}',
            ),
            const SizedBox(height: 12),
            ReportMetricCard(
              title: 'إجمالي المبيعات',
              value: totals.salesTotal,
              subtitle: 'العدد: ${totals.salesCount}',
            ),
            const SizedBox(height: 12),
            ReportMetricCard(
              title: 'الصافي',
              value: totals.netSalesMinusPurchases,
              subtitle: 'المبيعات - المشتريات',
            ),
            const SizedBox(height: 24),
            Text(
              'آخر العمليات',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 12),
            RecentTransactionsList(
              transactions: summary.recentTransactions,
            ),
          ],
        ),
      ),
    );
  }
}

class ReportMetricCard extends StatelessWidget {
  const ReportMetricCard({
    super.key,
    required this.title,
    required this.value,
    required this.subtitle,
  });

  final String title;
  final String value;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              title,
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            Text(
              value,
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 4),
            Text(
              subtitle,
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
  }
}

class RecentTransactionsList extends StatelessWidget {
  const RecentTransactionsList({
    super.key,
    required this.transactions,
  });

  final List<ReportRecentTransaction> transactions;

  @override
  Widget build(BuildContext context) {
    if (transactions.isEmpty) {
      return const Card(
        child: Padding(
          padding: EdgeInsets.all(16),
          child: Text('لا توجد عمليات حديثة.'),
        ),
      );
    }

    return Column(
      children: transactions
          .map(
            (tx) => Card(
              child: ListTile(
                title: Text(tx.reference.isEmpty ? tx.txType : tx.reference),
                subtitle: Text('${tx.date} ? ${tx.txTypeLabel}'),
                trailing: Text(tx.totalAmount),
              ),
            ),
          )
          .toList(),
    );
  }
}

class SalePage extends StatefulWidget {
  const SalePage({
    super.key,
    required this.auth,
  });

  final AuthResponse auth;

  @override
  State<SalePage> createState() => _SalePageState();
}

class _SalePageState extends State<SalePage> {
  final _api = const AuthApi();
  final _formKey = GlobalKey<FormState>();

  final _quantityController = TextEditingController(text: '1.00');
  final _unitPriceController = TextEditingController();

  String _kind = 'SHEEP';
  String _livestockClass = 'NONE';
  bool _isLoading = false;
  String? _errorMessage;
  PurchaseResponse? _saleResponse;

  static const _kindOptions = <_ChoiceItem>[
    _ChoiceItem(code: 'SHEEP', label: 'غنم'),
    _ChoiceItem(code: 'GOAT', label: 'ماعز'),
    _ChoiceItem(code: 'HARRI', label: 'طليان حري'),
    _ChoiceItem(code: 'SAWAKNI', label: 'طليان سواكني'),
    _ChoiceItem(code: 'NAIMI', label: 'طليان نعيمي'),
    _ChoiceItem(code: 'CAMEL', label: 'إبل'),
    _ChoiceItem(code: 'COW', label: 'بقر'),
  ];

  static const _classOptions = <_ChoiceItem>[
    _ChoiceItem(code: 'JADH', label: 'جذع'),
    _ChoiceItem(code: 'THANI', label: 'ثني'),
  ];

  bool get _requiresClass {
    return _requiresClassFor(_kind);
  }

  bool _requiresClassFor(String kind) {
    return kind == 'HARRI' || kind == 'SAWAKNI' || kind == 'NAIMI';
  }

  @override
  void dispose() {
    _quantityController.dispose();
    _unitPriceController.dispose();
    super.dispose();
  }

  void _onKindChanged(String? value) {
    if (value == null) {
      return;
    }

    setState(() {
      _kind = value;
      _livestockClass = _requiresClassFor(value) ? 'JADH' : 'NONE';
      _errorMessage = null;
      _saleResponse = null;
    });
  }

  String? _required(String? value, String message) {
    if (value == null || value.trim().isEmpty) {
      return message;
    }
    return null;
  }

  String? _positiveDecimal(String? value, String requiredMessage) {
    final requiredError = _required(value, requiredMessage);
    if (requiredError != null) {
      return requiredError;
    }

    final normalized = value!.trim().replaceAll(',', '.');
    final parsed = double.tryParse(normalized);

    if (parsed == null || parsed <= 0) {
      return 'الرقم يجب أن يكون أكبر من صفر';
    }

    return null;
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = null;
      _saleResponse = null;
    });

    try {
      final response = await _api.sale(
        token: widget.auth.token,
        kind: _kind,
        livestockClass: _livestockClass,
        quantity: _quantityController.text.trim().replaceAll(',', '.'),
        unitPrice: _unitPriceController.text.trim().replaceAll(',', '.'),
        idempotencyKey: 'flutter-sale-${DateTime.now().millisecondsSinceEpoch}',
      );

      if (!mounted) {
        return;
      }

      setState(() {
        _saleResponse = response;
      });
    } on AuthApiException catch (error) {
      if (!mounted) {
        return;
      }

      setState(() {
        _errorMessage = 'خطأ: ${error.message}';
      });
    } catch (error) {
      if (!mounted) {
        return;
      }

      setState(() {
        _errorMessage = 'خطأ: $error';
      });
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  void _openStock() {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => StockPage(auth: widget.auth),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final response = _saleResponse;

    return Directionality(
      textDirection: TextDirection.rtl,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('تسجيل بيع'),
        ),
        body: SafeArea(
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 520),
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Form(
                  key: _formKey,
                  child: ListView(
                    children: <Widget>[
                      Text(
                        'تسجيل بيع',
                        textAlign: TextAlign.center,
                        style: Theme.of(context).textTheme.headlineSmall,
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'الخادم: ${AuthApi.baseUrl}',
                        textAlign: TextAlign.center,
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                      const SizedBox(height: 32),
                      DropdownButtonFormField<String>(
                        initialValue: _kind,
                        decoration: const InputDecoration(
                          border: OutlineInputBorder(),
                          labelText: 'نوع المواشي',
                        ),
                        items: _kindOptions
                            .map(
                              (option) => DropdownMenuItem<String>(
                                value: option.code,
                                child: Text(option.label),
                              ),
                            )
                            .toList(),
                        onChanged: _isLoading ? null : _onKindChanged,
                      ),
                      if (_requiresClass) ...[
                        const SizedBox(height: 16),
                        DropdownButtonFormField<String>(
                          initialValue: _livestockClass,
                          decoration: const InputDecoration(
                            border: OutlineInputBorder(),
                            labelText: 'الصنف',
                          ),
                          items: _classOptions
                              .map(
                                (option) => DropdownMenuItem<String>(
                                  value: option.code,
                                  child: Text(option.label),
                                ),
                              )
                              .toList(),
                          onChanged: _isLoading
                              ? null
                              : (value) {
                                  if (value == null) {
                                    return;
                                  }
                                  setState(() {
                                    _livestockClass = value;
                                    _errorMessage = null;
                                    _saleResponse = null;
                                  });
                                },
                        ),
                      ],
                      const SizedBox(height: 16),
                      TextFormField(
                        controller: _quantityController,
                        keyboardType: const TextInputType.numberWithOptions(decimal: true),
                        textInputAction: TextInputAction.next,
                        decoration: const InputDecoration(
                          border: OutlineInputBorder(),
                          labelText: 'الكمية',
                        ),
                        validator: (value) => _positiveDecimal(
                          value,
                          'اكتب الكمية',
                        ),
                      ),
                      const SizedBox(height: 16),
                      TextFormField(
                        controller: _unitPriceController,
                        keyboardType: const TextInputType.numberWithOptions(decimal: true),
                        decoration: const InputDecoration(
                          border: OutlineInputBorder(),
                          labelText: 'سعر الوحدة',
                        ),
                        validator: (value) => _positiveDecimal(
                          value,
                          'اكتب سعر الوحدة',
                        ),
                        onFieldSubmitted: (_) => _submit(),
                      ),
                      const SizedBox(height: 24),
                      FilledButton(
                        onPressed: _isLoading || _saleResponse != null ? null : _submit,
                        child: _isLoading
                            ? const SizedBox(
                                width: 22,
                                height: 22,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              )
                            : const Text('حفظ البيع'),
                      ),
                      if (_errorMessage != null) ...[
                        const SizedBox(height: 24),
                        ErrorCard(message: _errorMessage!),
                      ],
                      if (response != null) ...[
                        const SizedBox(height: 24),
                        SaleSuccessCard(
                          response: response,
                          onOpenStock: _openStock,
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class SaleSuccessCard extends StatelessWidget {
  const SaleSuccessCard({
    super.key,
    required this.response,
    required this.onOpenStock,
  });

  final PurchaseResponse response;
  final VoidCallback onOpenStock;

  @override
  Widget build(BuildContext context) {
    final transaction = response.transaction;
    final line = response.line;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            const Text('تم تسجيل البيع بنجاح.'),
            const SizedBox(height: 12),
            InfoRow(label: 'المرجع', value: transaction.reference),
            const SizedBox(height: 8),
            InfoRow(label: 'الكمية', value: line.quantity),
            const SizedBox(height: 8),
            InfoRow(label: 'الإجمالي', value: transaction.totalAmount),
            const SizedBox(height: 16),
            OutlinedButton(
              onPressed: onOpenStock,
              child: const Text('عرض المخزون'),
            ),
          ],
        ),
      ),
    );
  }
}

class PurchasePage extends StatefulWidget {
  const PurchasePage({
    super.key,
    required this.auth,
  });

  final AuthResponse auth;

  @override
  State<PurchasePage> createState() => _PurchasePageState();
}

class _PurchasePageState extends State<PurchasePage> {
  final _api = const AuthApi();
  final _formKey = GlobalKey<FormState>();

  final _quantityController = TextEditingController(text: '1.00');
  final _unitPriceController = TextEditingController();

  String _kind = 'SHEEP';
  String _livestockClass = 'NONE';
  bool _isLoading = false;
  String? _errorMessage;
  PurchaseResponse? _purchaseResponse;

  static const _kindOptions = <_ChoiceItem>[
    _ChoiceItem(code: 'SHEEP', label: 'غنم'),
    _ChoiceItem(code: 'GOAT', label: 'ماعز'),
    _ChoiceItem(code: 'HARRI', label: 'طليان حري'),
    _ChoiceItem(code: 'SAWAKNI', label: 'طليان سواكني'),
    _ChoiceItem(code: 'NAIMI', label: 'طليان نعيمي'),
    _ChoiceItem(code: 'CAMEL', label: 'إبل'),
    _ChoiceItem(code: 'COW', label: 'بقر'),
  ];

  static const _classOptions = <_ChoiceItem>[
    _ChoiceItem(code: 'JADH', label: 'جذع'),
    _ChoiceItem(code: 'THANI', label: 'ثني'),
  ];

  bool get _requiresClass {
    return _requiresClassFor(_kind);
  }

  bool _requiresClassFor(String kind) {
    return kind == 'HARRI' || kind == 'SAWAKNI' || kind == 'NAIMI';
  }

  @override
  void dispose() {
    _quantityController.dispose();
    _unitPriceController.dispose();
    super.dispose();
  }

  void _onKindChanged(String? value) {
    if (value == null) {
      return;
    }

    setState(() {
      _kind = value;
      _livestockClass = _requiresClassFor(value) ? 'JADH' : 'NONE';
      _errorMessage = null;
      _purchaseResponse = null;
    });
  }

  String? _required(String? value, String message) {
    if (value == null || value.trim().isEmpty) {
      return message;
    }
    return null;
  }

  String? _positiveDecimal(String? value, String requiredMessage) {
    final requiredError = _required(value, requiredMessage);
    if (requiredError != null) {
      return requiredError;
    }

    final normalized = value!.trim().replaceAll(',', '.');
    final parsed = double.tryParse(normalized);

    if (parsed == null || parsed <= 0) {
      return 'الرقم يجب أن يكون أكبر من صفر';
    }

    return null;
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = null;
      _purchaseResponse = null;
    });

    try {
      final response = await _api.purchase(
        token: widget.auth.token,
        kind: _kind,
        livestockClass: _livestockClass,
        quantity: _quantityController.text.trim().replaceAll(',', '.'),
        unitPrice: _unitPriceController.text.trim().replaceAll(',', '.'),
        idempotencyKey: 'flutter-purchase-${DateTime.now().millisecondsSinceEpoch}',
      );

      if (!mounted) {
        return;
      }

      setState(() {
        _purchaseResponse = response;
      });
    } on AuthApiException catch (error) {
      if (!mounted) {
        return;
      }

      setState(() {
        _errorMessage = 'خطأ: ${error.message}';
      });
    } catch (error) {
      if (!mounted) {
        return;
      }

      setState(() {
        _errorMessage = 'خطأ: $error';
      });
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  void _openStock() {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => StockPage(auth: widget.auth),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final response = _purchaseResponse;

    return Directionality(
      textDirection: TextDirection.rtl,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('تسجيل شراء'),
        ),
        body: SafeArea(
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 520),
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Form(
                  key: _formKey,
                  child: ListView(
                    children: <Widget>[
                      Text(
                        'تسجيل شراء',
                        textAlign: TextAlign.center,
                        style: Theme.of(context).textTheme.headlineSmall,
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'الخادم: ${AuthApi.baseUrl}',
                        textAlign: TextAlign.center,
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                      const SizedBox(height: 32),
                      DropdownButtonFormField<String>(
                        initialValue: _kind,
                        decoration: const InputDecoration(
                          border: OutlineInputBorder(),
                          labelText: 'نوع المواشي',
                        ),
                        items: _kindOptions
                            .map(
                              (option) => DropdownMenuItem<String>(
                                value: option.code,
                                child: Text(option.label),
                              ),
                            )
                            .toList(),
                        onChanged: _isLoading ? null : _onKindChanged,
                      ),
                      if (_requiresClass) ...[
                        const SizedBox(height: 16),
                        DropdownButtonFormField<String>(
                          initialValue: _livestockClass,
                          decoration: const InputDecoration(
                            border: OutlineInputBorder(),
                            labelText: 'الصنف',
                          ),
                          items: _classOptions
                              .map(
                                (option) => DropdownMenuItem<String>(
                                  value: option.code,
                                  child: Text(option.label),
                                ),
                              )
                              .toList(),
                          onChanged: _isLoading
                              ? null
                              : (value) {
                                  if (value == null) {
                                    return;
                                  }
                                  setState(() {
                                    _livestockClass = value;
                                    _errorMessage = null;
                                    _purchaseResponse = null;
                                  });
                                },
                        ),
                      ],
                      const SizedBox(height: 16),
                      TextFormField(
                        controller: _quantityController,
                        keyboardType: const TextInputType.numberWithOptions(decimal: true),
                        textInputAction: TextInputAction.next,
                        decoration: const InputDecoration(
                          border: OutlineInputBorder(),
                          labelText: 'الكمية',
                        ),
                        validator: (value) => _positiveDecimal(
                          value,
                          'اكتب الكمية',
                        ),
                      ),
                      const SizedBox(height: 16),
                      TextFormField(
                        controller: _unitPriceController,
                        keyboardType: const TextInputType.numberWithOptions(decimal: true),
                        decoration: const InputDecoration(
                          border: OutlineInputBorder(),
                          labelText: 'سعر الوحدة',
                        ),
                        validator: (value) => _positiveDecimal(
                          value,
                          'اكتب سعر الوحدة',
                        ),
                        onFieldSubmitted: (_) => _submit(),
                      ),
                      const SizedBox(height: 24),
                      FilledButton(
                        onPressed: _isLoading || _purchaseResponse != null ? null : _submit,
                        child: _isLoading
                            ? const SizedBox(
                                width: 22,
                                height: 22,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              )
                            : const Text('حفظ الشراء'),
                      ),
                      if (_errorMessage != null) ...[
                        const SizedBox(height: 24),
                        ErrorCard(message: _errorMessage!),
                      ],
                      if (response != null) ...[
                        const SizedBox(height: 24),
                        PurchaseSuccessCard(
                          response: response,
                          onOpenStock: _openStock,
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class PurchaseSuccessCard extends StatelessWidget {
  const PurchaseSuccessCard({
    super.key,
    required this.response,
    required this.onOpenStock,
  });

  final PurchaseResponse response;
  final VoidCallback onOpenStock;

  @override
  Widget build(BuildContext context) {
    final transaction = response.transaction;
    final line = response.line;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            const Text('تم تسجيل الشراء بنجاح.'),
            const SizedBox(height: 12),
            InfoRow(label: 'المرجع', value: transaction.reference),
            const SizedBox(height: 8),
            InfoRow(label: 'الكمية', value: line.quantity),
            const SizedBox(height: 8),
            InfoRow(label: 'الإجمالي', value: transaction.totalAmount),
            const SizedBox(height: 16),
            OutlinedButton(
              onPressed: onOpenStock,
              child: const Text('عرض المخزون'),
            ),
          ],
        ),
      ),
    );
  }
}

class _ChoiceItem {
  const _ChoiceItem({
    required this.code,
    required this.label,
  });

  final String code;
  final String label;
}

class StockPage extends StatefulWidget {
  const StockPage({
    super.key,
    required this.auth,
  });

  final AuthResponse auth;

  @override
  State<StockPage> createState() => _StockPageState();
}

class _StockPageState extends State<StockPage> {
  final _api = const AuthApi();
  late Future<StockResponse> _stockFuture;

  @override
  void initState() {
    super.initState();
    _stockFuture = _api.stock(token: widget.auth.token);
  }

  void _refresh() {
    setState(() {
      _stockFuture = _api.stock(token: widget.auth.token);
    });
  }

  @override
  Widget build(BuildContext context) {
    return Directionality(
      textDirection: TextDirection.rtl,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('المخزون'),
          actions: <Widget>[
            IconButton(
              onPressed: _refresh,
              icon: const Icon(Icons.refresh),
              tooltip: 'تحديث',
            ),
          ],
        ),
        body: SafeArea(
          child: FutureBuilder<StockResponse>(
            future: _stockFuture,
            builder: (context, snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return const Center(child: CircularProgressIndicator());
              }

              if (snapshot.hasError) {
                return Center(
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 460),
                    child: Padding(
                      padding: const EdgeInsets.all(24),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: <Widget>[
                          ErrorCard(message: 'خطأ: ${snapshot.error}'),
                          const SizedBox(height: 16),
                          FilledButton(
                            onPressed: _refresh,
                            child: const Text('إعادة المحاولة'),
                          ),
                        ],
                      ),
                    ),
                  ),
                );
              }

              final stock = snapshot.data;
              if (stock == null) {
                return const Center(child: Text('لا توجد بيانات مخزون'));
              }

              return StockContent(stock: stock);
            },
          ),
        ),
      ),
    );
  }
}

class StockContent extends StatelessWidget {
  const StockContent({
    super.key,
    required this.stock,
  });

  final StockResponse stock;

  @override
  Widget build(BuildContext context) {
    final farmName = stock.farmName.isEmpty ? 'بدون منشأة' : stock.farmName;

    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 760),
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: ListView(
            children: <Widget>[
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Text(
                        'المخزون',
                        style: Theme.of(context).textTheme.headlineSmall,
                      ),
                      const SizedBox(height: 16),
                      InfoRow(label: 'المنشأة', value: farmName),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 24),
              if (stock.isEmpty)
                const Card(
                  child: Padding(
                    padding: EdgeInsets.all(20),
                    child: Text('لا يوجد مخزون حاليًا.'),
                  ),
                )
              else ...[
                Text(
                  'المخزون حسب النوع',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 12),
                for (final summary in stock.byKind) ...[
                  StockSummaryCard(summary: summary),
                  const SizedBox(height: 12),
                ],
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class StockSummaryCard extends StatelessWidget {
  const StockSummaryCard({
    super.key,
    required this.summary,
  });

  final StockKindSummary summary;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ExpansionTile(
        leading: const Icon(Icons.inventory_2_outlined),
        title: Text(summary.kindLabel),
        subtitle: Text('الإجمالي: ${summary.total}'),
        children: <Widget>[
          if (summary.classes.isEmpty)
            const Padding(
              padding: EdgeInsets.all(16),
              child: Text('لا توجد تفاصيل أصناف'),
            )
          else
            for (final item in summary.classes)
              ListTile(
                title: Text(item.classLabel),
                trailing: Text(item.quantity),
              ),
        ],
      ),
    );
  }
}

class HomeFeature {
  const HomeFeature({
    required this.title,
    required this.subtitle,
    required this.icon,
  });

  final String title;
  final String subtitle;
  final IconData icon;
}

class HomeFeatureCard extends StatelessWidget {
  const HomeFeatureCard({
    super.key,
    required this.feature,
    required this.onPressed,
  });

  final HomeFeature feature;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        leading: Icon(feature.icon),
        title: Text(feature.title),
        subtitle: Text(feature.subtitle),
        trailing: const Icon(Icons.chevron_left),
        onTap: onPressed,
      ),
    );
  }
}

class InfoRow extends StatelessWidget {
  const InfoRow({
    super.key,
    required this.label,
    required this.value,
  });

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: <Widget>[
        Text(
          '$label: ',
          style: const TextStyle(fontWeight: FontWeight.bold),
        ),
        Expanded(child: Text(value)),
      ],
    );
  }
}

class ErrorCard extends StatelessWidget {
  const ErrorCard({
    super.key,
    required this.message,
  });

  final String message;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Text(message),
      ),
    );
  }
}
