window.OTIMIZER_API_BASE = (window.Android && typeof window.Android.getApiBaseUrl === "function")
  ? window.Android.getApiBaseUrl()
  : "http://localhost:8000";
