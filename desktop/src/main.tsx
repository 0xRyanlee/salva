import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

// index.css 的 #root 進場動畫預設 opacity:0，要靠這行加上 app-ready 才會顯示
// （沿用 sparkie/src/main.tsx 的寫法，port 過來時漏了這步導致視窗永遠全白）。
requestAnimationFrame(() => {
  document.getElementById("root")?.classList.add("app-ready");
});
