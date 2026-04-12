const RUN_STATUS_LABELS = {
  queued: "排队中",
  running: "执行中",
  stopping: "停止中",
  succeeded: "已完成",
  failed: "失败",
  cancelled: "已取消",
};

const RECHARGE_STATUS_LABELS = {
  pending: "待审核",
  approved: "已通过",
  rejected: "已拒绝",
};

export function formatDateTime(value) {
  if (!value) {
    return "未记录";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  return date.toLocaleString();
}

export function formatMoneyCents(amountCents) {
  return `¥${((Number(amountCents) || 0) / 100).toFixed(2)}`;
}

export function formatDelta(delta) {
  const numeric = Number(delta) || 0;
  return numeric > 0 ? `+${numeric}` : `${numeric}`;
}

export function formatRunStatus(status) {
  return RUN_STATUS_LABELS[status] || status || "未知";
}

export function formatRechargeStatus(status) {
  return RECHARGE_STATUS_LABELS[status] || status || "未知";
}

export function formatAuthType(authType) {
  if (authType === "cookies") {
    return "Cookies";
  }
  if (authType === "password") {
    return "账号密码";
  }
  return authType || "未知";
}

export function extractErrorMessage(error) {
  if (typeof error === "string") {
    return error;
  }
  if (error && typeof error.message === "string") {
    return error.message;
  }
  return "操作失败，请稍后重试";
}

export function getCourseId(course) {
  return String(
    course?.courseId || course?.course_id || course?.id || course?.clazzId || course?.key || "",
  );
}

export function getCourseTitle(course) {
  return (
    course?.title ||
    course?.name ||
    course?.courseName ||
    course?.course_name ||
    getCourseId(course) ||
    "未命名课程"
  );
}

export function formatJsonPreview(value) {
  return JSON.stringify(value || {}, null, 2);
}
