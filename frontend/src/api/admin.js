import { apiRequest } from "./client";

export function listUsers() {
  return apiRequest("/admin/users");
}

export function updateUser(userId, payload) {
  return apiRequest(`/admin/users/${userId}`, {
    method: "PUT",
    data: payload,
  });
}

export function listAdminTasks() {
  return apiRequest("/admin/tasks");
}

export function listRechargeOrders() {
  return apiRequest("/admin/recharge-orders");
}

export function reviewRechargeOrder(orderId, payload) {
  return apiRequest(`/admin/recharge-orders/${orderId}`, {
    method: "PUT",
    data: payload,
  });
}

export function listInvites() {
  return apiRequest("/admin/invites");
}

export function createInvite(payload) {
  return apiRequest("/admin/invites", {
    method: "POST",
    data: payload,
  });
}

export function deleteInvite(inviteId) {
  return apiRequest(`/admin/invites/${inviteId}`, {
    method: "DELETE",
  });
}

export function listTikuProviders() {
  return apiRequest("/admin/tiku-providers");
}

export function createTikuProvider(payload) {
  return apiRequest("/admin/tiku-providers", {
    method: "POST",
    data: payload,
  });
}

export function listSystemSettings() {
  return apiRequest("/admin/settings");
}

export function updateSystemSetting(key, payload) {
  return apiRequest(`/admin/settings/${key}`, {
    method: "PUT",
    data: payload,
  });
}
