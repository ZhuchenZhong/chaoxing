import { apiRequest } from "./client";

export function listAccounts() {
  return apiRequest("/accounts");
}

export function createAccount(payload) {
  return apiRequest("/accounts", {
    method: "POST",
    data: payload,
  });
}

export function verifyAccount(accountId) {
  return apiRequest(`/accounts/${accountId}/verify`, {
    method: "POST",
  });
}

export function syncCourses(accountId) {
  return apiRequest(`/accounts/${accountId}/sync-courses`, {
    method: "POST",
  });
}

export function deleteAccount(accountId) {
  return apiRequest(`/accounts/${accountId}`, {
    method: "DELETE",
  });
}

export function listCourses(accountId) {
  return apiRequest(`/accounts/${accountId}/courses`);
}

export function getCourseChapters(accountId, courseId) {
  return apiRequest(`/accounts/${accountId}/courses/${courseId}/chapters`);
}
