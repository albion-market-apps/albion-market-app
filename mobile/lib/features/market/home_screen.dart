import 'package:easy_localization/easy_localization.dart';
import 'package:flutter/material.dart';

/// Tela inicial com busca placeholder.
/// TODO (fase 2): ligar ao client Dio (lib/core/api_client.dart, a criar)
/// consumindo GET /items da API, nos moldes do que a web já faz.
class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('home_title'.tr())),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextField(
              decoration: InputDecoration(
                hintText: 'search_placeholder'.tr(),
                border: const OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 16),
            Text('no_results'.tr(), style: Theme.of(context).textTheme.bodyMedium),
          ],
        ),
      ),
    );
  }
}
