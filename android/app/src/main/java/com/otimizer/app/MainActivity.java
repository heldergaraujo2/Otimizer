package com.otimizer.app;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ActivityNotFoundException;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Bundle;
import android.provider.Settings;
import android.view.Menu;
import android.view.MenuItem;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.EditText;
import android.widget.Toast;

import androidx.annotation.Nullable;
import androidx.webkit.WebViewAssetLoader;
import androidx.webkit.WebViewClientCompat;

public class MainActivity extends Activity {
    private static final int FILE_CHOOSER_REQUEST = 1001;
    private static final String PREFS = "otimizer";
    private static final String API_BASE_KEY = "api_base";
    private static final String DEFAULT_API_BASE = "http://10.0.2.2:8000";

    private WebView webView;
    private SharedPreferences preferences;
    private ValueCallback<Uri[]> filePathCallback;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        preferences = getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        setContentView(R.layout.activity_main);

        webView = findViewById(R.id.webview);
        configureWebView();
        webView.loadUrl("https://appassets.androidplatform.net/assets/index.html");
    }

    private void configureWebView() {
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setBuiltInZoomControls(false);
        settings.setDisplayZoomControls(false);
        // The first Android test connects the HTTPS WebView shell to a LAN HTTP backend.
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        settings.setUserAgentString(settings.getUserAgentString() + " OtimizerAndroid/0.1.0");

        WebViewAssetLoader assetLoader = new WebViewAssetLoader.Builder()
                .addPathHandler("/assets/", new WebViewAssetLoader.AssetsPathHandler(this))
                .build();

        webView.setWebViewClient(new WebViewClientCompat() {
            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                return assetLoader.shouldInterceptRequest(request.getUrl());
            }

            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view, String url) {
                return assetLoader.shouldInterceptRequest(Uri.parse(url));
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                return openExternalUrl(request.getUrl());
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, String url) {
                return openExternalUrl(Uri.parse(url));
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView webView, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (filePathCallback != null) {
                    filePathCallback.onReceiveValue(null);
                }
                filePathCallback = callback;
                Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                intent.setType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
                try {
                    startActivityForResult(intent, FILE_CHOOSER_REQUEST);
                    return true;
                } catch (ActivityNotFoundException ex) {
                    filePathCallback = null;
                    Toast.makeText(MainActivity.this, "Não foi possível abrir o seletor de arquivos.", Toast.LENGTH_LONG).show();
                    return false;
                }
            }
        });

        webView.addJavascriptInterface(new AndroidBridge(), "Android");
    }

    private boolean openExternalUrl(Uri uri) {
        String scheme = uri.getScheme();
        if (scheme == null || "https".equalsIgnoreCase(scheme) || "http".equalsIgnoreCase(scheme)
                || "geo".equalsIgnoreCase(scheme) || "google.navigation".equalsIgnoreCase(scheme)
                || "tel".equalsIgnoreCase(scheme) || "mailto".equalsIgnoreCase(scheme)) {
            try {
                Intent intent = new Intent(Intent.ACTION_VIEW, uri);
                startActivity(intent);
            } catch (ActivityNotFoundException ex) {
                Toast.makeText(this, "Não há aplicativo disponível para abrir este link.", Toast.LENGTH_LONG).show();
            }
            return true;
        }
        return false;
    }

    private String getApiBase() {
        String value = preferences.getString(API_BASE_KEY, DEFAULT_API_BASE);
        return value == null || value.trim().isEmpty() ? DEFAULT_API_BASE : value.trim();
    }

    private void showServerDialog() {
        final EditText input = new EditText(this);
        input.setSingleLine(true);
        input.setHint("http://192.168.1.10:8000");
        input.setText(getApiBase());
        input.setSelectAllOnFocus(true);

        new AlertDialog.Builder(this)
                .setTitle("Servidor do OTIMIZER")
                .setMessage("No teste com o PC, informe o endereço IP do computador na mesma rede Wi-Fi, seguido da porta 8000.")
                .setView(input)
                .setNegativeButton("Cancelar", null)
                .setPositiveButton("Salvar e recarregar", (dialog, which) -> {
                    String value = input.getText().toString().trim().replaceAll("/+$", "");
                    if (!(value.startsWith("http://") || value.startsWith("https://"))) {
                        Toast.makeText(this, "Use um endereço iniciado por http:// ou https://", Toast.LENGTH_LONG).show();
                        return;
                    }
                    preferences.edit().putString(API_BASE_KEY, value).apply();
                    webView.reload();
                })
                .show();
    }

    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        menu.add("Servidor").setShowAsAction(MenuItem.SHOW_AS_ACTION_IF_ROOM);
        menu.add("Recarregar").setShowAsAction(MenuItem.SHOW_AS_ACTION_NEVER);
        return true;
    }

    @Override
    public boolean onOptionsItemSelected(MenuItem item) {
        if ("Servidor".contentEquals(item.getTitle())) {
            showServerDialog();
            return true;
        }
        if ("Recarregar".contentEquals(item.getTitle())) {
            webView.reload();
            return true;
        }
        return super.onOptionsItemSelected(item);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != FILE_CHOOSER_REQUEST || filePathCallback == null) {
            return;
        }
        Uri[] results = null;
        if (resultCode == RESULT_OK && data != null) {
            Uri uri = data.getData();
            if (uri != null) {
                results = new Uri[]{uri};
            }
        }
        filePathCallback.onReceiveValue(results);
        filePathCallback = null;
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    private final class AndroidBridge {
        @JavascriptInterface
        public String getApiBaseUrl() {
            return getApiBase();
        }

        @JavascriptInterface
        public void openServerSettings() {
            runOnUiThread(MainActivity.this::showServerDialog);
        }
    }
}
