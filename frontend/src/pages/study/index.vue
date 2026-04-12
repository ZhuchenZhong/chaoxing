<template>
  <AppShell
    active-path="/pages/study/index"
    eyebrow="Study Runs"
    title="学习任务调度"
    subtitle="先选账号，再选课程，再创建运行。任务详情会持续轮询事件流。"
  >
    <template #actions>
      <button class="cx-inline-btn" @click="refreshPage">刷新任务</button>
    </template>

    <view v-if="errorMessage" class="cx-alert page-alert">{{ errorMessage }}</view>
    <view v-if="successMessage" class="cx-success page-alert">{{ successMessage }}</view>

    <view class="cx-grid cx-grid--double page-grid">
      <view class="cx-grid run-builder">
        <view class="cx-panel cx-panel--strong">
          <text class="cx-section-label">步骤 1</text>
          <text class="cx-panel-title">选择超星账号</text>
          <view v-if="workspace.accounts.length" class="selector-grid">
            <button
              v-for="account in workspace.accounts"
              :key="account.id"
              :class="['selector-card', Number(selectedAccountId) === account.id ? 'selector-card--active' : '']"
              @click="selectAccount(account.id)"
            >
              <text class="selector-title">{{ account.display_name || `账号 #${account.id}` }}</text>
              <text class="selector-meta">
                {{ formatAuthType(account.auth_type) }} · {{ account.is_login_valid ? "可用" : "待校验" }}
              </text>
            </button>
          </view>
          <view v-else class="cx-empty">请先到“超星账号”页绑定账号。</view>
        </view>

        <view class="cx-panel">
          <text class="cx-section-label">步骤 2</text>
          <text class="cx-panel-title">选择课程并创建运行</text>
          <view class="cx-form">
            <view>
              <text class="cx-field-label">可选课程</text>
              <view v-if="courses.length" class="course-list">
                <button
                  v-for="course in courses"
                  :key="getCourseId(course)"
                  :class="['course-card', isCourseSelected(getCourseId(course)) ? 'course-card--active' : '']"
                  @click="toggleCourse(getCourseId(course))"
                >
                  <text class="selector-title">{{ getCourseTitle(course) }}</text>
                  <text class="selector-meta">课程 ID: {{ getCourseId(course) }}</text>
                </button>
              </view>
              <view v-else class="cx-empty">
                {{ selectedAccountId ? "暂无课程，请先执行课程同步。" : "先选择一个账号。" }}
              </view>
            </view>
            <view>
              <text class="cx-field-label">Profile ID（可选）</text>
              <input
                v-model="profileId"
                class="cx-input"
                placeholder="不填则使用默认 profile"
                type="number"
              />
            </view>
            <button class="cx-primary-btn" :disabled="busyAction" @click="submitRun">
              {{ busyAction ? "创建中..." : "创建学习运行" }}
            </button>
          </view>
        </view>
      </view>

      <view class="cx-grid run-inspector">
        <view class="cx-panel">
          <text class="cx-section-label">最近运行</text>
          <text class="cx-panel-title">任务队列</text>
          <LoadingSpinner v-if="!initialized" text="加载任务..." />
          <view v-else-if="workspace.runs.length" class="cx-list">
            <view
              v-for="run in workspace.runs"
              :key="run.id"
              :class="['cx-list-item', selectedRunId === run.id ? 'cx-list-item--selected' : '']"
            >
              <view class="cx-item-top">
                <view>
                  <text class="cx-item-title">运行 #{{ run.id }}</text>
                  <text class="cx-item-meta">
                    账号 {{ run.account_id }} · 课程 {{ run.course_ids?.join(", ") || "未选" }}
                  </text>
                </view>
                <text :class="['status-pill', statusClass(run.status)]">
                  {{ formatRunStatus(run.status) }}
                </text>
              </view>
              <ProgressBar
                v-if="getRunProgress(run).percent > 0 || ['running', 'queued'].includes(run.status)"
                :percent="getRunProgress(run).percent"
                :status="run.status"
              />
              <text v-if="getRunProgress(run).currentItem" class="cx-item-meta run-progress-hint">
                {{ getRunProgress(run).currentItem }}
              </text>
              <view class="account-actions">
                <button class="cx-inline-btn" @click="openRun(run.id)">查看详情</button>
                <button
                  v-if="['queued', 'running', 'stopping'].includes(run.status)"
                  class="cx-danger-btn"
                  :disabled="busyAction"
                  @click="cancelRunAction(run.id)"
                >
                  取消
                </button>
              </view>
            </view>
          </view>
          <EmptyState
            v-else
            icon="📋"
            title="暂无学习运行"
            description="从左侧选择账号和课程后创建一条运行。"
          />
        </view>

        <view class="cx-panel" style="position: relative;">
          <text class="cx-section-label">运行详情</text>
          <text class="cx-panel-title">
            {{ selectedRunDetail ? `运行 #${selectedRunDetail.id}` : "选择一条运行查看事件流" }}
          </text>
          <LoadingSpinner v-if="loadingDetail" text="加载详情..." :overlay="!!selectedRunDetail" />
          <view v-if="selectedRunDetail" class="detail-stack">
            <view class="detail-summary">
              <view class="detail-summary-row">
                <text class="cx-field-label">状态</text>
                <text :class="['status-pill', statusClass(selectedRunDetail.status)]">
                  {{ formatRunStatus(selectedRunDetail.status) }}
                </text>
              </view>
              <view class="detail-summary-row">
                <text class="cx-field-label">创建时间</text>
                <text class="cx-item-meta">{{ formatDateTime(selectedRunDetail.created_at) }}</text>
              </view>
              <view v-if="selectedRunDetail.finished_at" class="detail-summary-row">
                <text class="cx-field-label">完成时间</text>
                <text class="cx-item-meta">{{ formatDateTime(selectedRunDetail.finished_at) }}</text>
              </view>
            </view>
            <view v-if="detailProgress.percent > 0 || ['running', 'queued'].includes(selectedRunDetail.status)" class="detail-block">
              <text class="cx-field-label">进度</text>
              <ProgressBar :percent="detailProgress.percent" :status="selectedRunDetail.status" />
              <text v-if="detailProgress.currentItem" class="cx-item-meta">
                {{ detailProgress.currentItem }}
              </text>
            </view>
            <view v-if="['queued', 'running', 'stopping'].includes(selectedRunDetail.status)" class="detail-block">
              <button
                class="cx-danger-btn"
                :disabled="busyAction"
                @click="cancelRunAction(selectedRunDetail.id)"
              >
                取消此运行
              </button>
            </view>
            <view class="detail-block">
              <text class="cx-field-label">事件流</text>
              <view v-if="selectedRunDetail.events && selectedRunDetail.events.length" class="cx-list">
                <view
                  v-for="event in selectedRunDetail.events"
                  :key="event.id"
                  class="cx-list-item"
                >
                  <view class="cx-item-top">
                    <text class="cx-item-title">{{ event.message }}</text>
                    <text :class="['status-pill', event.level === 'error' ? 'status-pill--bad' : event.level === 'warning' ? 'status-pill--warn' : 'status-pill--ok']">
                      {{ event.level }}
                    </text>
                  </view>
                  <text class="cx-item-meta">{{ formatDateTime(event.created_at) }}</text>
                </view>
              </view>
              <view v-else class="cx-empty">当前运行还没有事件。</view>
            </view>
            <view class="detail-block">
              <text class="cx-field-label">进度 JSON</text>
              <text class="detail-json">{{ formatJsonPreview(selectedRunDetail.progress_json) }}</text>
            </view>
          </view>
          <EmptyState
            v-else-if="!loadingDetail"
            icon="🔍"
            title="选择一条运行"
            description="从左侧任务列表点开一条运行即可查看详情。"
          />
        </view>
      </view>
    </view>
  </AppShell>
</template>

<script setup>
import { computed, ref } from "vue";
import { onHide, onShow, onUnload } from "@dcloudio/uni-app";

import AppShell from "../../components/AppShell.vue";
import EmptyState from "../../components/EmptyState.vue";
import LoadingSpinner from "../../components/LoadingSpinner.vue";
import ProgressBar from "../../components/ProgressBar.vue";
import { useSessionStore } from "../../store/session";
import { useWorkspaceStore } from "../../store/workspace";
import { requireSession } from "../../utils/access";
import {
  extractErrorMessage,
  formatAuthType,
  formatDateTime,
  formatJsonPreview,
  formatRunStatus,
  getCourseId,
  getCourseTitle,
} from "../../utils/display";

const session = useSessionStore();
const workspace = useWorkspaceStore();

const selectedAccountId = ref("");
const selectedCourseIds = ref([]);
const selectedRunId = ref(0);
const profileId = ref("");
const errorMessage = ref("");
const successMessage = ref("");
const busyAction = ref(false);
const loadingDetail = ref(false);
const initialized = ref(false);

let pollTimer = null;

const courses = computed(() => workspace.coursesByAccount[selectedAccountId.value] || []);
const selectedRunDetail = computed(() =>
  selectedRunId.value ? workspace.runDetails[selectedRunId.value] || null : null,
);

const detailProgress = computed(() => getRunProgress(selectedRunDetail.value));

function getRunProgress(run) {
  if (!run) return { percent: 0, currentItem: "" };
  const pj = run.progress_json || run.progress || {};
  const total = Number(pj.total_chapters || pj.total || 0);
  const done = Number(pj.completed_chapters || pj.completed || pj.done || 0);
  const percent = total > 0 ? Math.round((done / total) * 100) : 0;
  const currentCourse = pj.current_course || pj.course_name || "";
  const currentChapter = pj.current_chapter || pj.chapter_name || "";
  let currentItem = "";
  if (currentCourse || currentChapter) {
    currentItem = [currentCourse, currentChapter].filter(Boolean).join(" → ");
  } else if (total > 0) {
    currentItem = `已完成 ${done} / ${total} 章节`;
  }
  return { percent, currentItem };
}

onShow(async () => {
  await refreshPage();
  startPolling();
});

onHide(stopPolling);
onUnload(stopPolling);

async function refreshPage() {
  if (!(await requireSession(session, { allowPasswordReset: false }))) {
    return;
  }
  errorMessage.value = "";
  try {
    await Promise.all([workspace.loadAccounts(), workspace.loadRuns()]);
    if (!selectedAccountId.value && workspace.accounts.length) {
      selectedAccountId.value = String(workspace.accounts[0].id);
    }
    if (selectedAccountId.value) {
      await workspace.loadCourses(Number(selectedAccountId.value));
    }
    if (selectedRunId.value) {
      await workspace.loadRunDetail(selectedRunId.value);
    }
  } catch (error) {
    errorMessage.value = extractErrorMessage(error);
  } finally {
    initialized.value = true;
  }
}

async function selectAccount(accountId) {
  selectedAccountId.value = String(accountId);
  selectedCourseIds.value = [];
  errorMessage.value = "";
  try {
    await workspace.loadCourses(accountId);
  } catch (error) {
    errorMessage.value = extractErrorMessage(error);
  }
}

function toggleCourse(courseId) {
  if (!courseId) {
    return;
  }
  if (selectedCourseIds.value.includes(courseId)) {
    selectedCourseIds.value = selectedCourseIds.value.filter((item) => item !== courseId);
    return;
  }
  selectedCourseIds.value = [...selectedCourseIds.value, courseId];
}

function isCourseSelected(courseId) {
  return selectedCourseIds.value.includes(courseId);
}

async function submitRun() {
  if (!selectedAccountId.value) {
    errorMessage.value = "请先选择一个账号";
    return;
  }
  if (!selectedCourseIds.value.length) {
    errorMessage.value = "至少选择一门课程";
    return;
  }

  busyAction.value = true;
  errorMessage.value = "";
  successMessage.value = "";
  try {
    const run = await workspace.createRun({
      account_id: Number(selectedAccountId.value),
      course_ids: selectedCourseIds.value,
      profile_id: profileId.value ? Number(profileId.value) : null,
    });
    selectedRunId.value = run.id;
    await workspace.loadRunDetail(run.id);
    successMessage.value = `学习运行 #${run.id} 已创建。`;
  } catch (error) {
    errorMessage.value = extractErrorMessage(error);
  } finally {
    busyAction.value = false;
  }
}

async function openRun(runId) {
  loadingDetail.value = true;
  errorMessage.value = "";
  try {
    selectedRunId.value = runId;
    await workspace.loadRunDetail(runId);
  } catch (error) {
    errorMessage.value = extractErrorMessage(error);
  } finally {
    loadingDetail.value = false;
  }
}

async function cancelRunAction(runId) {
  busyAction.value = true;
  errorMessage.value = "";
  successMessage.value = "";
  try {
    await workspace.cancelRun(runId);
    if (selectedRunId.value === runId) {
      await workspace.loadRunDetail(runId);
    }
    successMessage.value = `运行 #${runId} 已标记为取消。`;
  } catch (error) {
    errorMessage.value = extractErrorMessage(error);
  } finally {
    busyAction.value = false;
  }
}

function startPolling() {
  stopPolling();
  pollTimer = setInterval(async () => {
    if (!session.isAuthenticated) {
      return;
    }
    try {
      await workspace.loadRuns();
      if (selectedRunId.value) {
        await workspace.loadRunDetail(selectedRunId.value);
      }
    } catch (_error) {
    }
  }, 5000);
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

function statusClass(status) {
  if (status === "succeeded") {
    return "status-pill--ok";
  }
  if (status === "failed" || status === "cancelled") {
    return "status-pill--bad";
  }
  return "status-pill--warn";
}
</script>

<style>
.page-grid,
.page-alert {
  margin-top: 24rpx;
}

.run-builder,
.run-inspector {
  align-content: start;
}

.selector-grid,
.course-list {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}

.selector-card,
.course-card {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
  padding: 22rpx 24rpx;
  border: 1px solid rgba(76, 53, 32, 0.1);
  border-radius: 22rpx;
  background: rgba(255, 252, 247, 0.72);
  text-align: left;
}

.selector-card--active,
.course-card--active {
  border-color: rgba(157, 79, 31, 0.35);
  background: rgba(255, 246, 235, 0.94);
  box-shadow: 0 12rpx 28rpx rgba(157, 79, 31, 0.12);
}

.selector-title {
  font-size: 28rpx;
  font-weight: 700;
  line-height: 1.4;
}

.selector-meta {
  color: var(--cx-muted);
  font-size: 22rpx;
  line-height: 1.6;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  padding: 10rpx 18rpx;
  border-radius: 999rpx;
  font-size: 20rpx;
  font-weight: 700;
}

.status-pill--warn {
  background: rgba(157, 79, 31, 0.12);
  color: var(--cx-accent-dark);
}

.status-pill--ok {
  background: rgba(48, 82, 67, 0.12);
  color: var(--cx-olive);
}

.status-pill--bad {
  background: rgba(157, 47, 47, 0.1);
  color: var(--cx-alert);
}

.detail-stack {
  display: flex;
  flex-direction: column;
  gap: 18rpx;
}

.detail-block {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.detail-json {
  padding: 20rpx;
  border-radius: 18rpx;
  background: rgba(36, 27, 21, 0.06);
  font-family: "IBM Plex Sans", monospace;
  font-size: 22rpx;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

.account-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 14rpx;
}

.cx-list-item--selected {
  border-color: rgba(157, 79, 31, 0.35);
  background: rgba(255, 246, 235, 0.94);
}

.run-progress-hint {
  font-style: italic;
}

.detail-summary {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
  padding: 18rpx 20rpx;
  border-radius: 18rpx;
  background: rgba(36, 27, 21, 0.04);
}

.detail-summary-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12rpx;
}
</style>
