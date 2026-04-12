<template>
  <AppShell
    active-path="/pages/index/index"
    eyebrow="Workspace"
    title="你的学习工作台"
    subtitle="账户状态、任务队列、积分余额和近期流水都在这一页汇总。"
  >
    <template #actions>
      <button class="cx-inline-btn" :disabled="loading" @click="refreshDashboard">
        {{ loading ? "刷新中..." : "刷新概览" }}
      </button>
    </template>

    <LoadingSpinner v-if="loading && !initialized" text="加载工作台..." />

    <template v-if="initialized">
      <view class="cx-grid metrics-grid">
      <view class="cx-panel metric-card">
        <text class="cx-metric-label">超星账号</text>
        <text class="cx-metric-value">{{ workspace.accounts.length }}</text>
        <text class="cx-field-hint">已接入的学习通账户数</text>
      </view>
      <view class="cx-panel metric-card">
        <text class="cx-metric-label">执行中任务</text>
        <text class="cx-metric-value">{{ workspace.runningRuns.length }}</text>
        <text class="cx-field-hint">当前排队、执行或停止中的学习任务</text>
      </view>
      <view class="cx-panel metric-card">
        <text class="cx-metric-label">已完成</text>
        <text class="cx-metric-value">{{ workspace.completedRuns.length }}</text>
        <text class="cx-field-hint">成功完成的学习运行</text>
      </view>
      <view class="cx-panel metric-card">
        <text class="cx-metric-label">钱包余额</text>
        <text class="cx-metric-value">{{ walletBalance }}</text>
        <text class="cx-field-hint">系统积分余额</text>
      </view>
    </view>

    <view v-if="errorMessage" class="cx-alert dashboard-alert">{{ errorMessage }}</view>

    <view class="cx-grid cx-grid--double dashboard-sections">
      <view class="cx-panel cx-panel--strong">
        <text class="cx-section-label">快速动作</text>
        <text class="cx-panel-title">先把账号和课程准备好</text>
        <text class="cx-panel-subtitle">
          普通用户的闭环是：重绑账号、同步课程、创建任务、回看事件流。
        </text>
        <view class="action-row">
          <button class="cx-primary-btn" @click="openPage('/pages/accounts/index')">管理账号</button>
          <button class="cx-ghost-btn" @click="openPage('/pages/study/index')">新建任务</button>
          <button class="cx-ghost-btn" @click="openPage('/pages/settings/index')">学习设置</button>
        </view>
      </view>

      <view class="cx-panel">
        <text class="cx-section-label">账户关注</text>
        <text class="cx-panel-title">优先处理登录失效的账户</text>
        <view v-if="workspace.invalidAccounts.length" class="cx-list">
          <view
            v-for="account in workspace.invalidAccounts"
            :key="account.id"
            class="cx-list-item"
          >
            <view class="cx-item-top">
              <view>
                <text class="cx-item-title">{{ account.display_name || `账号 #${account.id}` }}</text>
                <text class="cx-item-meta">
                  {{ formatAuthType(account.auth_type) }} · 最近同步 {{ formatDateTime(account.last_synced_at) }}
                </text>
              </view>
              <text class="status-pill status-pill--warn">待校验</text>
            </view>
          </view>
        </view>
        <view v-else class="cx-empty">当前所有账户都处于可用状态。</view>
      </view>

      <view class="cx-panel">
        <text class="cx-section-label">近期任务</text>
        <text class="cx-panel-title">最近提交的学习运行</text>
        <view v-if="recentRuns.length" class="cx-list">
          <view v-for="run in recentRuns" :key="run.id" class="cx-list-item">
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
            <text class="cx-item-meta">创建于 {{ formatDateTime(run.created_at) }}</text>
          </view>
        </view>
        <view v-else class="cx-empty">还没有学习任务。去“学习任务”页先创建一条。</view>
      </view>

      <view class="cx-panel">
        <text class="cx-section-label">最近流水</text>
        <text class="cx-panel-title">钱包变动历史</text>
        <view v-if="recentTransactions.length" class="cx-list">
          <view
            v-for="transaction in recentTransactions"
            :key="transaction.id"
            class="cx-list-item"
          >
            <view class="cx-item-top">
              <view>
                <text class="cx-item-title">{{ transaction.reason }}</text>
                <text class="cx-item-meta">{{ formatDateTime(transaction.created_at) }}</text>
              </view>
              <text :class="['delta-chip', Number(transaction.delta) >= 0 ? 'delta-chip--up' : 'delta-chip--down']">
                {{ formatDelta(transaction.delta) }}
              </text>
            </view>
            <text class="cx-item-meta">余额变为 {{ transaction.balance_after }}</text>
          </view>
        </view>
        <view v-else class="cx-empty">还没有钱包流水。</view>
      </view>
    </view>
    </template>
  </AppShell>
</template>

<script setup>
import { computed, ref } from "vue";
import { onShow } from "@dcloudio/uni-app";

import AppShell from "../../components/AppShell.vue";
import LoadingSpinner from "../../components/LoadingSpinner.vue";
import { useSessionStore } from "../../store/session";
import { useWorkspaceStore } from "../../store/workspace";
import {
  extractErrorMessage,
  formatAuthType,
  formatDateTime,
  formatDelta,
  formatRunStatus,
} from "../../utils/display";
import { requireSession } from "../../utils/access";

const session = useSessionStore();
const workspace = useWorkspaceStore();

const loading = ref(false);
const initialized = ref(false);
const errorMessage = ref("");

const walletBalance = computed(() => workspace.wallet?.balance ?? 0);
const recentRuns = computed(() => workspace.runs.slice(0, 5));
const recentTransactions = computed(() => workspace.walletTransactions.slice(0, 6));

onShow(async () => {
  await refreshDashboard();
});

async function refreshDashboard() {
  if (!(await requireSession(session, { allowPasswordReset: false }))) {
    return;
  }
  loading.value = true;
  errorMessage.value = "";
  try {
    await Promise.all([workspace.loadDashboard(), workspace.loadWalletHistory()]);
  } catch (error) {
    errorMessage.value = extractErrorMessage(error);
  } finally {
    loading.value = false;
    initialized.value = true;
  }
}

function openPage(path) {
  uni.reLaunch({ url: path });
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
.metrics-grid {
  margin-top: 24rpx;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.metric-card {
  min-height: 220rpx;
  justify-content: space-between;
}

.dashboard-alert {
  margin-top: 22rpx;
}

.dashboard-sections {
  margin-top: 24rpx;
}

.action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 14rpx;
}

.status-pill,
.delta-chip {
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

.status-pill--ok,
.delta-chip--up {
  background: rgba(48, 82, 67, 0.12);
  color: var(--cx-olive);
}

.status-pill--bad,
.delta-chip--down {
  background: rgba(157, 47, 47, 0.1);
  color: var(--cx-alert);
}

@media (max-width: 959px) {
  .metrics-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
