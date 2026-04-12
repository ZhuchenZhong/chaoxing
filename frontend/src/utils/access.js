export async function requireSession(session, options = {}) {
  const { admin = false, allowPasswordReset = true } = options;
  await session.bootstrap();

  if (!session.isAuthenticated) {
    uni.reLaunch({ url: "/pages/login/index" });
    return false;
  }

  if (!allowPasswordReset && session.needsPasswordReset) {
    uni.reLaunch({ url: "/pages/login/index" });
    return false;
  }

  if (admin && !session.isAdmin) {
    uni.reLaunch({ url: "/pages/index/index" });
    return false;
  }

  return true;
}
