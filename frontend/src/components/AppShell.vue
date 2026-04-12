<template>
  <view class="cx-shell">
    <view class="cx-topbar">
      <view class="cx-brand-row">
        <view>
          <text class="cx-kicker">{{ eyebrow }}</text>
          <text class="cx-title">{{ title }}</text>
          <text class="cx-subtitle">{{ subtitle }}</text>
        </view>
        <slot name="actions" />
      </view>

      <view class="cx-meta" v-if="session.isAuthenticated">
        <view class="cx-row">
          <text :class="['cx-user-chip', session.isAdmin ? 'cx-user-chip--admin' : '']">
            {{ session.user?.display_name || session.user?.username }}
          </text>
          <text
            v-if="session.needsPasswordReset"
            class="cx-status-chip"
          >
            需要首次改密
          </text>
          <text
            v-else-if="session.isAdmin"
            class="cx-status-chip cx-status-chip--admin"
          >
            管理员入口已启用
          </text>
        </view>
        <button class="cx-inline-btn" @click="session.logout()">退出登录</button>
      </view>

      <view class="cx-nav" v-if="session.isAuthenticated">
        <button
          v-for="item in navigationItems"
          :key="item.path"
          :class="['cx-nav-btn', item.path === activePath ? 'cx-nav-btn--active' : '']"
          @click="openPage(item.path)"
        >
          {{ item.label }}
        </button>
      </view>
    </view>

    <slot />

    <view class="cx-footer-mark" @click="openDeerflow">Created By Deerflow</view>
  </view>
</template>

<script setup>
import { computed } from "vue";

import { useSessionStore } from "../store/session";

const props = defineProps({
  activePath: {
    type: String,
    default: "",
  },
  eyebrow: {
    type: String,
    default: "Chaoxing Web",
  },
  title: {
    type: String,
    required: true,
  },
  subtitle: {
    type: String,
    default: "",
  },
});

const session = useSessionStore();

const navigationItems = computed(() => {
  const items = [
    { label: "工作台", path: "/pages/index/index" },
    { label: "超星账号", path: "/pages/accounts/index" },
    { label: "学习任务", path: "/pages/study/index" },
    { label: "设置", path: "/pages/settings/index" },
  ];
  if (session.isAdmin) {
    items.push({ label: "管理员", path: "/pages/admin/index" });
  }
  return items;
});

function openPage(path) {
  if (path === props.activePath) {
    return;
  }
  uni.reLaunch({ url: path });
}

function openDeerflow() {
  if (typeof window !== "undefined") {
    window.open("https://deerflow.tech", "_blank");
  }
}
</script>
