<template>
  <view class="cx-empty-state">
    <text class="cx-empty-state-icon">{{ icon }}</text>
    <text class="cx-empty-state-title">{{ title }}</text>
    <text v-if="description" class="cx-empty-state-desc">{{ description }}</text>
    <slot />
  </view>
</template>

<script setup>
defineProps({
  icon: {
    type: String,
    default: "📭",
  },
  title: {
    type: String,
    required: true,
  },
  description: {
    type: String,
    default: "",
  },
});
</script>

<style>
.cx-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14rpx;
  padding: 48rpx 24rpx;
  border-radius: 22rpx;
  background: rgba(255, 253, 249, 0.76);
  text-align: center;
}

.cx-empty-state-icon {
  font-size: 56rpx;
  line-height: 1;
}

.cx-empty-state-title {
  color: var(--cx-text);
  font-size: 28rpx;
  font-weight: 600;
  line-height: 1.5;
}

.cx-empty-state-desc {
  color: var(--cx-muted);
  font-size: 24rpx;
  line-height: 1.7;
  max-width: 80%;
}
</style>
