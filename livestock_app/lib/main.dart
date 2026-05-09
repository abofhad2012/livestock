import 'package:flutter/material.dart';

import 'api/auth_api.dart';

void main() {
  runApp(const LivestockApp());
}

class LivestockApp extends StatelessWidget {
  const LivestockApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'محاسبة المواشي',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        colorSchemeSeed: Colors.green,
      ),
      home: const LoginPage(),
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

class LoginPage extends StatefulWidget {
  const LoginPage({super.key});

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final _api = const AuthApi();
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

      if (!mounted) {
        return;
      }

      openHome(context, response);
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
    return Directionality(
      textDirection: TextDirection.rtl,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('محاسبة المواشي'),
        ),
        body: SafeArea(
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Form(
                  key: _formKey,
                  child: ListView(
                    shrinkWrap: true,
                    children: <Widget>[
                      const Text(
                        'تسجيل الدخول',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          fontSize: 28,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'الخادم: ${AuthApi.baseUrl}',
                        textAlign: TextAlign.center,
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                      const SizedBox(height: 32),
                      TextFormField(
                        controller: _usernameController,
                        textInputAction: TextInputAction.next,
                        decoration: const InputDecoration(
                          border: OutlineInputBorder(),
                          labelText: 'اسم المستخدم',
                        ),
                        validator: (value) {
                          if (value == null || value.trim().isEmpty) {
                            return 'اكتب اسم المستخدم';
                          }
                          return null;
                        },
                      ),
                      const SizedBox(height: 16),
                      TextFormField(
                        controller: _passwordController,
                        obscureText: true,
                        decoration: const InputDecoration(
                          border: OutlineInputBorder(),
                          labelText: 'كلمة المرور',
                        ),
                        validator: (value) {
                          if (value == null || value.isEmpty) {
                            return 'اكتب كلمة المرور';
                          }
                          return null;
                        },
                        onFieldSubmitted: (_) => _submit(),
                      ),
                      const SizedBox(height: 24),
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
                      const SizedBox(height: 12),
                      TextButton(
                        onPressed: _isLoading ? null : _openRegister,
                        child: const Text('إنشاء حساب جديد'),
                      ),
                      if (_errorMessage != null) ...[
                        const SizedBox(height: 24),
                        ErrorCard(message: _errorMessage!),
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

class RegisterPage extends StatefulWidget {
  const RegisterPage({super.key});

  @override
  State<RegisterPage> createState() => _RegisterPageState();
}

class _RegisterPageState extends State<RegisterPage> {
  final _api = const AuthApi();
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

      if (!mounted) {
        return;
      }

      openHome(context, response);
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

  String? _required(String? value, String message) {
    if (value == null || value.trim().isEmpty) {
      return message;
    }
    return null;
  }

  String? _passwordValidator(String? value) {
    if (value == null || value.isEmpty) {
      return 'اكتب كلمة المرور';
    }
    if (value.length < 8) {
      return 'كلمة المرور يجب ألا تقل عن 8 أحرف';
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    return Directionality(
      textDirection: TextDirection.rtl,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('تسجيل حساب جديد'),
        ),
        body: SafeArea(
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 460),
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Form(
                  key: _formKey,
                  child: ListView(
                    shrinkWrap: true,
                    children: <Widget>[
                      const Text(
                        'تسجيل حساب جديد',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          fontSize: 28,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'الخادم: ${AuthApi.baseUrl}',
                        textAlign: TextAlign.center,
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                      const SizedBox(height: 32),
                      TextFormField(
                        controller: _usernameController,
                        textInputAction: TextInputAction.next,
                        decoration: const InputDecoration(
                          border: OutlineInputBorder(),
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
                        textInputAction: TextInputAction.next,
                        decoration: const InputDecoration(
                          border: OutlineInputBorder(),
                          labelText: 'كلمة المرور',
                        ),
                        validator: _passwordValidator,
                      ),
                      const SizedBox(height: 16),
                      TextFormField(
                        controller: _fullNameController,
                        textInputAction: TextInputAction.next,
                        decoration: const InputDecoration(
                          border: OutlineInputBorder(),
                          labelText: 'الاسم الكامل',
                        ),
                      ),
                      const SizedBox(height: 16),
                      TextFormField(
                        controller: _phoneController,
                        textInputAction: TextInputAction.next,
                        keyboardType: TextInputType.phone,
                        decoration: const InputDecoration(
                          border: OutlineInputBorder(),
                          labelText: 'رقم الجوال',
                        ),
                      ),
                      const SizedBox(height: 16),
                      TextFormField(
                        controller: _farmNameController,
                        decoration: const InputDecoration(
                          border: OutlineInputBorder(),
                          labelText: 'اسم المنشأة',
                        ),
                        validator: (value) => _required(
                          value,
                          'اكتب اسم المنشأة',
                        ),
                        onFieldSubmitted: (_) => _submit(),
                      ),
                      const SizedBox(height: 24),
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
                      const SizedBox(height: 12),
                      TextButton(
                        onPressed: _isLoading ? null : () => Navigator.pop(context),
                        child: const Text('العودة لتسجيل الدخول'),
                      ),
                      if (_errorMessage != null) ...[
                        const SizedBox(height: 24),
                        ErrorCard(message: _errorMessage!),
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

class HomePage extends StatelessWidget {
  const HomePage({
    super.key,
    required this.auth,
  });

  final AuthResponse auth;

  String get username {
    final fullName = (auth.user['full_name'] ?? '').toString().trim();
    if (fullName.isNotEmpty) {
      return fullName;
    }
    return (auth.user['username'] ?? 'مستخدم').toString();
  }

  String get farmName {
    return (auth.farm?['name'] ?? 'بدون منشأة').toString();
  }

  @override
  Widget build(BuildContext context) {
    final features = <HomeFeature>[
      const HomeFeature(
        title: 'المخزون',
        subtitle: 'عرض مخزون المواشي',
        icon: Icons.inventory_2_outlined,
      ),
      const HomeFeature(
        title: 'شراء',
        subtitle: 'تسجيل عملية شراء',
        icon: Icons.add_shopping_cart,
      ),
      const HomeFeature(
        title: 'بيع',
        subtitle: 'تسجيل عملية بيع',
        icon: Icons.point_of_sale,
      ),
    ];

    return Directionality(
      textDirection: TextDirection.rtl,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('الرئيسية'),
        ),
        body: SafeArea(
          child: Center(
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
                              'مرحبًا',
                              style: Theme.of(context).textTheme.headlineSmall,
                            ),
                            const SizedBox(height: 16),
                            InfoRow(label: 'المستخدم', value: username),
                            const SizedBox(height: 8),
                            InfoRow(label: 'المنشأة', value: farmName),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 24),
                    Text(
                      'العمليات',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(height: 12),
                    HomeFeatureCard(
                      feature: features[0],
                      onPressed: () {
                        Navigator.of(context).push(
                          MaterialPageRoute<void>(
                            builder: (_) => StockPage(auth: auth),
                          ),
                        );
                      },
                    ),
                    const SizedBox(height: 12),
                    HomeFeatureCard(
                      feature: features[1],
                      onPressed: () {
                        Navigator.of(context).push(
                          MaterialPageRoute<void>(
                            builder: (_) => PurchasePage(auth: auth),
                          ),
                        );
                      },
                    ),
                    const SizedBox(height: 12),
                    HomeFeatureCard(
                      feature: features[2],
                      onPressed: () {
                        Navigator.of(context).push(
                          MaterialPageRoute<void>(
                            builder: (_) => SalePage(auth: auth),
                          ),
                        );
                      },
                    ),
                    const SizedBox(height: 12),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
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
