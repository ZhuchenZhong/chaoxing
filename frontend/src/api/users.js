import { apiRequest } from "./client";

export function getProfile() {
  return apiRequest("/users/profile");
}

export function updateProfile(payload) {
  return apiRequest("/users/profile", {
    method: "PUT",
    data: payload,
  });
}
