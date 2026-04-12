const TOKEN_STORAGE_KEY = "chaoxing-web-tokens";
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api/v1").replace(
  /\/$/,
  "",
);

let refreshPromise = null;

function rawRequest(path, options = {}) {
  return new Promise((resolve, reject) => {
    uni.request({
      url: `${API_BASE_URL}${path}`,
      method: options.method || "GET",
      data: options.data,
      header: options.header,
      success: resolve,
      fail: reject,
    });
  });
}

export function getStoredTokens() {
  const tokenState = uni.getStorageSync(TOKEN_STORAGE_KEY);
  if (!tokenState) {
    return { accessToken: "", refreshToken: "" };
  }
  return {
    accessToken: tokenState.accessToken || "",
    refreshToken: tokenState.refreshToken || "",
  };
}

export function setStoredTokens(tokens) {
  uni.setStorageSync(TOKEN_STORAGE_KEY, {
    accessToken: tokens.access_token || tokens.accessToken || "",
    refreshToken: tokens.refresh_token || tokens.refreshToken || "",
  });
}

export function clearStoredTokens() {
  uni.removeStorageSync(TOKEN_STORAGE_KEY);
}

async function refreshAccessToken() {
  const { refreshToken } = getStoredTokens();
  if (!refreshToken) {
    throw new Error("Missing refresh token");
  }

  if (!refreshPromise) {
    refreshPromise = rawRequest("/auth/refresh", {
      method: "POST",
      data: { refresh_token: refreshToken },
      header: {
        "Content-Type": "application/json",
      },
    })
      .then((response) => {
        if (response.statusCode >= 400) {
          throw new Error("Session refresh failed");
        }
        setStoredTokens(response.data);
        return response.data;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }

  return refreshPromise;
}

function buildErrorMessage(response) {
  const { data, statusCode } = response;
  if (typeof data === "string" && data.trim()) {
    return data;
  }
  if (data && typeof data === "object") {
    if (typeof data.detail === "string") {
      return data.detail;
    }
    if (typeof data.message === "string") {
      return data.message;
    }
  }
  return `Request failed with status ${statusCode}`;
}

export async function apiRequest(path, options = {}) {
  const { auth = true, retry = true, method = "GET", data, header = {} } = options;
  const tokens = getStoredTokens();
  const requestHeaders = {
    "Content-Type": "application/json",
    ...header,
  };
  if (auth && tokens.accessToken) {
    requestHeaders.Authorization = `Bearer ${tokens.accessToken}`;
  }

  const response = await rawRequest(path, { method, data, header: requestHeaders });
  if (response.statusCode === 401 && auth && retry && tokens.refreshToken) {
    try {
      await refreshAccessToken();
      return await apiRequest(path, { ...options, retry: false });
    } catch (error) {
      clearStoredTokens();
      throw error;
    }
  }

  if (response.statusCode >= 400) {
    throw new Error(buildErrorMessage(response));
  }
  return response.data;
}

export function getApiBaseUrl() {
  return API_BASE_URL;
}
