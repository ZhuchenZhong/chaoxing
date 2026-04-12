import { apiRequest } from "./client";

export function login(payload) {
  return apiRequest("/auth/login", {
    method: "POST",
    auth: false,
    data: payload,
  });
}

export function fetchCurrentUser() {
  return apiRequest("/auth/me");
}

export function register(payload) {
  return apiRequest("/auth/register", {
    method: "POST",
    auth: false,
    data: payload,
  });
}

export function changePassword(payload) {
  return apiRequest("/auth/change-password", {
    method: "POST",
    data: payload,
  });
}
