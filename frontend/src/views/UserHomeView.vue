<template>
  <section>
    <div class="page-heading">
      <div>
        <p class="eyebrow">用户工作台</p>
        <h1>我的反馈</h1>
        <p>提交问题、查看处理进度，并对解决结果进行确认。</p>
      </div>
      <button class="button button-primary" type="button">提交新反馈</button>
    </div>
    <div class="card-grid">
      <article class="metric-card"><span>待处理</span><strong>—</strong><small>等待后端工单接口接入</small></article>
      <article class="metric-card"><span>处理中</span><strong>—</strong><small>仅展示当前用户数据</small></article>
      <article class="metric-card"><span>待确认</span><strong>—</strong><small>可确认解决或重新打开</small></article>
    </div>
    <div class="content-card placeholder-card">工单列表区域由 5 号成员继续实现。</div>
  </section>
</template>
