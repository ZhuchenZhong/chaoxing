<template>
  <AppShell
    active-path="/pages/accounts/index"
    eyebrow="Accounts"
    title="超星账号管理"
    subtitle="迁移过来的历史账号关系已经保留，但需要在这里重新绑定或重新校验。"
  >
    <template #actions>
      <button class="cx-inline-btn" :disabled="loading" @click="loadPage">
        {{ loading ? "刷新中..." : "刷新账号" }}
      </button>
    </template>

    <view v-if="errorMessage" class="cx-alert page-alert">{{ errorMessage }}</view>
    <view v-if="successMessage" class="cx-success page-alert">{{ successMessage }}</view>

    <LoadingSpinner v-if="loading && !initialized" text="加载账号..." />

    <view v-if="initialized" class="cx-grid cx-grid--double page-grid">
      <view class="cx-panel cx-panel--strong">
        <text class="cx-section-label">新增账号</text>
        <text class="cx-panel-title">重新绑定新的登录凭据</text>
        <text class="cx-panel-subtitle">
          密码登录适合日常使用；Cookies 登录适合临时恢复。Cookies 输入框需要标准 JSON。
        </text>

        <view class="auth-type-row">
          <button
            :class="['cx-nav-btn', accountForm.auth_type === 'password' ? 'cx-nav-btn--active' : '']"
            @click="accountForm.auth_type = 'password'"
          >
            账号密码
          </button>
          <button
            :class="['cx-nav-btn', accountForm.auth_type === 'cookies' ? 'cx-nav-btn--active' : '']"
            @click="accountForm.auth_type = 'cookies'"
          >
            Cookies
          </button>
        </view>

        <view class="cx-form">
          <view>
            <text class="cx-field-label">显示名称</text>
            <input
              v-model="accountForm.display_name"
              class="cx-input"
              placeholder="例如：主账号 / 课程刷课号"
            />
          </view>

          <template v-if="accountForm.auth_type === 'password'">
            <view>
              <text class="cx-field-label">超星用户名</text>
              <input
                v-model="accountForm.username"
                class="cx-input"
                placeholder="手机号、学号或用户名"
              />
            </view>
            <view>
              <text class="cx-field-label">超星密码</text>
              <input
                v-model="accountForm.password"
                class="cx-input"
                password
                placeholder="输入超星密码"
              />
            </view>
          </template>

          <view v-else>
            <text class="cx-field-label">Cookies JSON</text>
            <textarea
              v-model="accountForm.cookies_json"
              class="cx-textarea"
              placeholder='{"UID":"...","_uid":"..."}'
            />
          </view>

          <button class="cx-primary-btn" :disabled="busyAction" @click="submitAccount">
            {{ busyAction ? "提交中..." : "保存账号" }}
          </button>
        </view>
      </view>

      <view class="cx-panel">
        <text class="cx-section-label">已有账号</text>
        <text class="cx-panel-title">管理历史绑定和校验状态</text>
        <view v-if="workspace.accounts.length" class="cx-list">
          <view v-for="account in workspace.accounts" :key="account.id" class="cx-list-item">
            <view class="cx-item-top">
              <view>
                <text class="cx-item-title">{{ account.display_name || `账号 #${account.id}` }}</text>
                <text class="cx-item-meta">
                  {{ formatAuthType(account.auth_type) }} · 最近同步 {{ formatDateTime(account.last_synced_at) }}
                </text>
              </view>
              <text :class="['status-pill', account.is_login_valid ? 'status-pill--ok' : 'status-pill--warn']">
                {{ account.is_login_valid ? "可用" : "待校验" }}
              </text>
            </view>
            <view class="account-actions">
              <button class="cx-inline-btn" :disabled="busyAction" @click="verifyExisting(account.id)">
                校验登录
              </button>
              <button class="cx-inline-btn" :disabled="busyAction" @click="syncExisting(account.id)">
                同步课程
              </button>
              <button class="cx-danger-btn" :disabled="busyAction" @click="removeExisting(account.id)">
                删除
              </button>
            </view>
          </view>
        </view>
        <EmptyState v-else title="暂无账号" description="还没有绑定任何超星账号。在左侧面板添加新账号开始使用。" />
      </view>
    </view>
  </AppShell>
</template>

<script setup>
import { reactive, ref } from "vue";
import { onShow } from "@dcloudio/uni-app";

import AppShell from "../../components/AppShell.vue";
import LoadingSpinner from "../../components/LoadingSpinner.vue";
import EmptyState from "../../components/EmptyState.vue";
import { useSessionStore } from "../../store/session";
import { useWorkspaceStore } from "../../store/workspace";
import { requireSession } from "../../utils/access";
import { extractErrorMessage, formatAuthType, formatDateTime } from "../../utils/display";
import { parseJsonInput } from "../../utils/json";

const session = useSessionStore();
const workspace = useWorkspaceStore();

const loading = ref(false);
const initialized = ref(false);
const busyAction = ref(false);
const errorMessage = ref("");
const successMessage = ref("");

const accountForm = reactive({
  display_name: "",
  auth_type: "password",
  username: "",
  password: "",
  cookies_json: '{\n  "UID": "",\n  "_uid": ""\n}',
});

onShow(async () => {
  await loadPage();
});

async function loadPage() {
  if (!(await requireSession(session, { allowPasswordReset: false }))) {
    return;
  }
  loading.value = true;
  errorMessage.value = "";
  try {
    await workspace.loadAccounts();
  } catch (error) {
    errorMessage.value = extractErrorMessage(error);
  } finally {
    loading.value = false;
    initialized.value = true;
  }
}

async function submitAccount() {
  busyAction.value = true;
  errorMessage.value = "";
  successMessage.value = "";
  try {
    const payload = {
      display_name: accountForm.display_name || null,
      auth_type: accountForm.auth_type,
    };
    if (accountForm.auth_type === "password") {
      payload.username = accountForm.username.trim();
      payload.password = accountForm.password;
    } else {
      payload.cookies = parseJsonInput(accountForm.cookies_json, {});
    }
    await workspace.addAccount(payload);
    resetForm();
    successMessage.value = "账号已保存。建议立刻执行一次登录校验。";
  } catch (error) {
    errorMessage.value = extractErrorMessage(error);
  } finally {
    busyAction.value = false;
  }
}

async function verifyExisting(accountId) {
  busyAction.value = true;
  errorMessage.value = "";
  successMessage.value = "";
  try {
    const result = await workspace.pingAccount(accountId);
    successMessage.value = result.message || "校验完成";
  } catch (error) {
    errorMessage.value = extractErrorMessage(error);
  } finally {
    busyAction.value = false;
  }
}

async function syncExisting(accountId) {
  busyAction.value = true;
  errorMessage.value = "";
  successMessage.value = "";
  try {
    const result = await workspace.refreshAccountCourses(accountId);
    successMessage.value = `同步完成，共获取 ${result.course_count} 门课程。`;
  } catch (error) {
    errorMessage.value = extractErrorMessage(error);
  } finally {
    busyAction.value = false;
  }
}

async function removeExisting(accountId) {
  const confirmResult = await confirmAction("删除后需要重新绑定，确定继续吗？");
  if (!confirmResult) {
    return;
  }

  busyAction.value = true;
  errorMessage.value = "";
  successMessage.value = "";
  try {
    await workspace.removeAccount(accountId);
    successMessage.value = "账号已删除。";
  } catch (error) {
    errorMessage.value = extractErrorMessage(error);
  } finally {
    busyAction.value = false;
  }
}

function resetForm() {
  accountForm.display_name = "";
  accountForm.username = "";
  accountForm.password = "";
  accountForm.cookies_json = '{\n  "UID": "",\n  "_uid": ""\n}';
}

function confirmAction(content) {
  return new Promise((resolve) => {
    uni.showModal({
      title: "确认操作",
      content,
      success: (result) => resolve(Boolean(result.confirm)),
      fail: () => resolve(false),
    });
  });
}
</script>

<style>
.page-grid,
.page-alert {
  margin-top: 24rpx;
}

.auth-type-row,
.account-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 14rpx;
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
</style>
