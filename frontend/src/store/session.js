import { computed, ref } from "vue";
import { defineStore } from "pinia";

import { changePassword, fetchCurrentUser, login } from "../api/auth";
import { clearStoredTokens, getStoredTokens, setStoredTokens } from "../api/client";

const USER_STORAGE_KEY = "chaoxing-web-user";

function readStoredUser() {
  return uni.getStorageSync(USER_STORAGE_KEY) || null;
}

function writeStoredUser(user) {
  if (user) {
    uni.setStorageSync(USER_STORAGE_KEY, user);
    return;
  }
  uni.removeStorageSync(USER_STORAGE_KEY);
}

export const useSessionStore = defineStore("session", () => {
  const tokens = ref(getStoredTokens());
  const user = ref(readStoredUser());
  const ready = ref(false);

  const isAuthenticated = computed(() => Boolean(tokens.value.accessToken && user.value));
  const isAdmin = computed(() => user.value?.role === "admin");
  const needsPasswordReset = computed(() => Boolean(user.value?.must_change_password));

  function syncTokenState() {
    tokens.value = getStoredTokens();
  }

  function clearSession() {
    clearStoredTokens();
    writeStoredUser(null);
    syncTokenState();
    user.value = null;
  }

  async function bootstrap() {
    if (ready.value) {
      return;
    }
    ready.value = true;
    syncTokenState();
    if (!tokens.value.accessToken) {
      user.value = null;
      writeStoredUser(null);
      return;
    }
    try {
      user.value = await fetchCurrentUser();
      writeStoredUser(user.value);
    } catch (_error) {
      clearSession();
    }
  }

  async function loginWithPassword(username, password) {
    const tokenPayload = await login({ username, password });
    setStoredTokens(tokenPayload);
    syncTokenState();
    user.value = await fetchCurrentUser();
    writeStoredUser(user.value);
    return user.value;
  }

  async function rotatePassword(currentPassword, newPassword) {
    user.value = await changePassword({
      current_password: currentPassword,
      new_password: newPassword,
    });
    writeStoredUser(user.value);
    return user.value;
  }

  function logout() {
    clearSession();
    uni.reLaunch({ url: "/pages/login/index" });
  }

  return {
    user,
    ready,
    tokens,
    isAuthenticated,
    isAdmin,
    needsPasswordReset,
    bootstrap,
    loginWithPassword,
    rotatePassword,
    logout,
    clearSession,
  };
});
