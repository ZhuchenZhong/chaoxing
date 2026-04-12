import { apiRequest } from "./client";

export function getStudyConfig() {
  return apiRequest("/users/study-config");
}

export function updateStudyConfig(payload) {
  return apiRequest("/users/study-config", {
    method: "PUT",
    data: payload,
  });
}

export function getTikuConfig() {
  return apiRequest("/users/tiku-config");
}

export function updateTikuConfig(payload) {
  return apiRequest("/users/tiku-config", {
    method: "PUT",
    data: payload,
  });
}
