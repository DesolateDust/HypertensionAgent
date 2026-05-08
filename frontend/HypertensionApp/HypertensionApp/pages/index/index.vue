<template>
	<view class="app-container">
		
		<view v-if="!isLoggedIn" class="login-page">
			<view class="login-header">
				<image class="logo" src="/static/logo.png" mode="aspectFit"></image>
				<text class="app-name">高血压健康管家</text>
				<text class="slogan">您的端侧 AI 伴诊专家</text>
			</view>
			
			<view class="login-form">
				<text class="label">请选择登录账号：</text>
				<picker @change="onUserChange" :value="userIndex" :range="userList" class="user-picker-login">
					<view class="picker-inner">{{ userList[userIndex] || '正在拉取账号...' }} ▼</view>
				</picker>
				
				<button class="login-btn" @click="doLogin" :disabled="userList.length === 0">授权登录 (端侧模式)</button>
			</view>
		</view>

		<view v-else class="chat-page">
			<view class="nav-bar">
				<text class="title">❤️ 健康管家 ({{ currentUser }})</text>
				<text class="logout-text" @click="doLogout">退出</text>
			</view>

			<scroll-view class="chat-box" scroll-y="true" :scroll-top="scrollTop" scroll-with-animation>
				<view v-for="(msg, index) in messages" :key="index" :class="['message-wrapper', msg.type]">
					<image v-if="msg.type === 'ai' || msg.type === 'alert'" class="avatar" src="/static/logo.png" mode="aspectFit"></image>
					<view :class="['bubble', msg.type]"><text class="msg-text">{{ msg.content }}</text></view>
					<image v-if="msg.type === 'user'" class="avatar" src="/static/logo.png" style="opacity: 0;"></image>
				</view>
				<view style="height: 20px;"></view>
			</scroll-view>

			<view class="input-area">
				<input class="input-box" v-model="inputText" placeholder="描述您的症状或提问..." @confirm="sendMessage" confirm-type="send"/>
				<button class="send-btn" :disabled="!inputText" @click="sendMessage">发送</button>
			</view>
		</view>

	</view>
</template>

<script>
export default {
	data() {
		return {
			apiBase: "http://127.0.0.1:8000",
			isLoggedIn: false, // 控制页面切换的核心变量
			userList: [],
			userIndex: 0,
			currentUser: "",
			inputText: "",
			scrollTop: 0,
			messages: [],
			alertTimer: null
		}
	},
	onLoad() {
		this.fetchUsers();
	},
	methods: {
		fetchUsers() {
			uni.request({
				url: `${this.apiBase}/api/users`,
				success: (res) => {
					if(res.data && res.data.users) {
						this.userList = res.data.users;
						let targetIdx = this.userList.indexOf('stress_non_dipper_10days_user');
						if(targetIdx !== -1) this.userIndex = targetIdx;
					}
				}
			});
		},
		onUserChange(e) {
			this.userIndex = e.detail.value;
		},
		doLogin() {
			this.currentUser = this.userList[this.userIndex];
			this.isLoggedIn = true;
			this.messages = [
				{ type: 'ai', content: `【登录成功】已加载设备绑定档案：${this.currentUser}。后台传感器连接正常，我将全天候守护您的血压健康。` }
			];
			// 开启轮询
			if(this.alertTimer) clearInterval(this.alertTimer);
			this.alertTimer = setInterval(this.checkAlerts, 3000);
		},
		doLogout() {
			this.isLoggedIn = false;
			if(this.alertTimer) clearInterval(this.alertTimer);
		},
		sendMessage() {
			if (!this.inputText.trim()) return;
			const text = this.inputText;
			this.messages.push({ type: 'user', content: text });
			this.inputText = "";
			this.scrollToBottom();

			uni.request({
				url: `${this.apiBase}/api/chat`,
				method: 'POST',
				data: { user_id: this.currentUser, message: text },
				success: (res) => {
					this.messages.push({ type: 'ai', content: res.data.reply || "网络连接异常" });
					this.scrollToBottom();
				},
				fail: () => {
					this.messages.push({ type: 'alert', content: "网络请求失败，请检查后端是否运行。" });
				}
			});
		},
		checkAlerts() {
			uni.request({
				url: `${this.apiBase}/api/get_alert?user_id=${this.currentUser}`,
				success: (res) => {
					if(res.data && res.data.alert) {
						this.messages.push({ type: 'alert', content: "【紧急预警】 " + res.data.alert });
						this.scrollToBottom();
					}
				}
			});
		},
		scrollToBottom() {
			setTimeout(() => { this.scrollTop = this.messages.length * 1000; }, 100);
		}
	}
}
</script>

<style>
page { background-color: #f5f5f5; height: 100%; }
.app-container { height: 100vh; }

/* 登录页样式 */
.login-page { height: 100%; display: flex; flex-direction: column; justify-content: center; align-items: center; background-color: white; padding: 30px; }
.login-header { align-items: center; display: flex; flex-direction: column; margin-bottom: 50px; }
.logo { width: 80px; height: 80px; margin-bottom: 15px; border-radius: 20px; background-color: #f0f0f0;}
.app-name { font-size: 24px; font-weight: bold; color: #333; margin-bottom: 5px; }
.slogan { font-size: 14px; color: #888; }
.login-form { width: 100%; }
.label { font-size: 14px; color: #666; margin-bottom: 10px; display: block; }
.user-picker-login { background-color: #f8f9fa; border: 1px solid #e9ecef; border-radius: 8px; padding: 15px; margin-bottom: 30px; }
.picker-inner { text-align: center; font-size: 16px; color: #333; font-weight: bold; }
.login-btn { background-color: #07c160; color: white; border-radius: 25px; height: 50px; line-height: 50px; font-size: 18px; width: 100%; }

/* 聊天页样式 */
.chat-page { display: flex; flex-direction: column; height: 100vh; }
.nav-bar { background-color: #07c160; color: white; padding: 45px 15px 15px 15px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); z-index: 10; }
.title { font-size: 16px; font-weight: bold; }
.logout-text { font-size: 14px; opacity: 0.9; }
.chat-box { flex: 1; padding: 15px; box-sizing: border-box; }
.message-wrapper { display: flex; margin-bottom: 20px; align-items: flex-start; }
.message-wrapper.user { justify-content: flex-end; }
.avatar { width: 40px; height: 40px; border-radius: 5px; margin: 0 10px; background-color: white; }
.bubble { max-width: 70%; padding: 12px 15px; border-radius: 8px; font-size: 15px; line-height: 1.5; word-wrap: break-word;}
.bubble.ai { background-color: white; color: #333; border-top-left-radius: 0; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
.bubble.user { background-color: #95ec69; color: #333; border-top-right-radius: 0; }
.bubble.alert { background-color: #fff3cd; color: #d32f2f; border-left: 4px solid #d32f2f; border-top-left-radius: 0; font-weight: bold; box-shadow: 0 2px 8px rgba(211,47,47,0.2); }
.input-area { background-color: #f7f7f7; padding: 10px 15px 25px 15px; display: flex; align-items: center; border-top: 1px solid #e5e5e5; }
.input-box { flex: 1; background-color: white; height: 40px; border-radius: 20px; padding: 0 15px; font-size: 15px; margin-right: 10px; }
.send-btn { width: 60px; height: 40px; background-color: #07c160; color: white; border-radius: 20px; font-size: 14px; display: flex; justify-content: center; align-items: center; padding: 0;}
.send-btn[disabled] { background-color: #a8e9c0; }
</style>