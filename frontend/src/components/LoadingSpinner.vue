<template>
  <view class="cx-loading" :class="{ 'cx-loading--overlay': overlay }">
    <view class="cx-loading-spinner" />
    <text v-if="text" class="cx-loading-text">{{ text }}</text>
  </view>
</template>

<script setup>
defineProps({
  text: {
    type: String,
    default: "加载中...",
  },
  overlay: {
    type: Boolean,
    default: false,
  },
});
</script>

<style>
.cx-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16rpx;
  padding: 40rpx 20rpx;
}

.cx-loading--overlay {
  position: absolute;
  inset: 0;
  z-index: 10;
  background: rgba(239, 228, 207, 0.7);
  backdrop-filter: blur(4px);
  border-radius: var(--cx-radius-md);
}

.cx-loading-spinner {
  width: 48rpx;
  height: 48rpx;
  border: 4rpx solid rgba(157, 79, 31, 0.2);
  border-top-color: var(--cx-accent);
  border-radius: 50%;
  animation: cx-spin 0.7s linear infinite;
}

.cx-loading-text {
  color: var(--cx-muted);
  font-size: 24rpx;
}

@keyframes cx-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
