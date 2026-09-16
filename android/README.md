# OTIMIZER Android — primeiro teste

O APK é um invólucro Android do frontend atual. O processamento continua no backend OTIMIZER; o celular apenas executa a interface, seleciona a planilha e abre a navegação externa quando solicitado.

## Primeiro teste usando o PC como backend

1. Deixe o celular e o PC na mesma rede Wi-Fi.
2. No PC, descubra o IPv4 local (por exemplo `192.168.1.10`).
3. Inicie o backend escutando na rede, não somente em `127.0.0.1`.
4. Configure o CORS do backend antes de iniciar o servidor:

```text
OTIMIZER_CORS_ORIGINS=http://localhost:3000,http://localhost:5173,http://localhost:8080,http://127.0.0.1:8080,https://appassets.androidplatform.net
```

5. Instale o APK no Android.
6. Abra **Servidor** no menu do app e informe `http://IP_DO_PC:8000`.
7. Faça login, selecione um `.xlsx` e execute a otimização.

O endereço do servidor fica salvo no celular para os próximos testes.

## APK

O workflow **Android APK** gera `app-debug.apk` como artefato do GitHub Actions. Este é um APK de teste, não uma versão de distribuição da Play Store.
