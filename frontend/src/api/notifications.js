import { apiRequest } from "./client";

export function getNotificationConfig() {
  return apiRequest("/users/notification-config");
}

export function updateNotificationConfig(payload) {
  return apiRequest("/users/notification-config", {
    method: "PUT",
    data: payload,
  });
}

export function testNotification() {
  return apiRequest("/users/notification-config/test", {
    method: "POST",
  });
}
