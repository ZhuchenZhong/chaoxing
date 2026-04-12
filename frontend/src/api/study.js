import { apiRequest } from "./client";

export function listStudyRuns() {
  return apiRequest("/study-runs");
}

export function getStudyRun(runId) {
  return apiRequest(`/study-runs/${runId}`);
}

export function createStudyRun(payload) {
  return apiRequest("/study-runs", {
    method: "POST",
    data: payload,
  });
}

export function cancelStudyRun(runId) {
  return apiRequest(`/study-runs/${runId}/cancel`, {
    method: "POST",
  });
}
