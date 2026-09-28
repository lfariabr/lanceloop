const cameraStatus = document.querySelector("#camera-status");
const bufferLabel = document.querySelector("#buffer-label");
const bufferFill = document.querySelector("#buffer-fill");
const bufferProgress = document.querySelector("#buffer-progress");
const bufferNote = document.querySelector("#buffer-note");
const saveButton = document.querySelector("#save-button");
const actionMessage = document.querySelector("#action-message");
const replayList = document.querySelector("#replay-list");

let saving = false;
let replayCount = 0;

async function refreshStatus() {
  try {
    const response = await fetch("/health", { cache: "no-store" });
    if (!response.ok) throw new Error("Cannot reach the camera service");
    const status = await response.json();
    const seconds = Math.min(status.buffered_seconds, status.replay_seconds);
    const percentage = Math.min(100, (seconds / status.replay_seconds) * 100);

    bufferLabel.textContent = `${seconds.toFixed(1)} / ${status.replay_seconds}s`;
    bufferFill.style.width = `${percentage}%`;
    bufferProgress.setAttribute("aria-valuenow", String(seconds));
    cameraStatus.textContent = status.connected ? "CONNECTED" : "WAITING FOR CAMERA";
    cameraStatus.classList.toggle("connected", status.connected);
    bufferNote.textContent = status.error || (status.ready ? "Replay ready. Press save after the play." : "Filling the replay buffer…");
    saveButton.disabled = !status.ready || saving;
  } catch (error) {
    cameraStatus.textContent = "SERVER OFFLINE";
    cameraStatus.classList.remove("connected");
    bufferNote.textContent = error.message;
    saveButton.disabled = true;
  }
}

saveButton.addEventListener("click", async () => {
  saving = true;
  saveButton.disabled = true;
  actionMessage.textContent = "Saving your replay…";
  actionMessage.classList.remove("error");
  try {
    const response = await fetch("/replays", { method: "POST" });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Could not save replay");

    replayCount += 1;
    if (replayCount === 1) replayList.replaceChildren();
    const item = document.createElement("li");
    const link = document.createElement("a");
    const number = document.createElement("span");
    const time = document.createElement("small");
    number.textContent = `REPLAY ${String(replayCount).padStart(2, "0")}`;
    time.textContent = `${result.seconds}s · ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
    link.href = result.url;
    link.download = "";
    link.append(number, time);
    item.append(link);
    replayList.prepend(item);
    actionMessage.textContent = "Replay saved. Select it below to download.";
  } catch (error) {
    actionMessage.textContent = error.message;
    actionMessage.classList.add("error");
  } finally {
    saving = false;
    refreshStatus();
  }
});

refreshStatus();
setInterval(refreshStatus, 1000);
