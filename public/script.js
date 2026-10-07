const API = '';  // نفس السيرفر
let adminKey = localStorage.getItem('admin_key') || '';
let cart = JSON.parse(localStorage.getItem('real_cart') || '[]');

// ===== المنتجات =====
async function loadProducts() {
  const grid = document.getElementById('products-grid');
  if (!grid) return;
  try {
    const res = await fetch(API + '/api/products');
    const products = await res.json();
    if (!products.length) {
      grid.innerHTML = '<p class="empty-msg">لا توجد منتجات حالياً.</p>';
      return;
    }
    grid.innerHTML = products.map(p => `
      <div class="product-card">
        <div class="product-image">
          ${p.image ? `<img src="${p.image}" alt="${p.name}" onerror="this.parentElement.innerHTML='📦'">` : '📦'}
        </div>
        <div class="product-info">
          <h3>${p.name}</h3>
          <p>${p.description || ''}</p>
          <div class="product-price">${p.price} ر.س</div>
          <button class="add-to-cart" onclick="addToCart(${p.id}, '${p.name.replace(/'/g, "\\'")}', ${p.price})">أضف إلى السلة</button>
        </div>
      </div>
    `).join('');
  } catch (e) {
    grid.innerHTML = '<p class="empty-msg">خطأ في الاتصال بالسيرفر. تأكد أن السيرفر يعمل.</p>';
  }
}

// ===== السلة =====
function saveCart() {
  localStorage.setItem('real_cart', JSON.stringify(cart));
  updateCartCount();
}

function updateCartCount() {
  const el = document.getElementById('cart-count');
  if (el) el.textContent = cart.reduce((s, i) => s + i.qty, 0);
}

function addToCart(id, name, price) {
  const existing = cart.find(i => i.id === id);
  if (existing) existing.qty++;
  else cart.push({ id, name, price, qty: 1 });
  saveCart();
  renderCart();
  document.getElementById('cart-sidebar')?.classList.add('open');
  document.getElementById('overlay')?.classList.add('show');
}

function removeFromCart(id) {
  cart = cart.filter(i => i.id !== id);
  saveCart();
  renderCart();
}

function renderCart() {
  const container = document.getElementById('cart-items');
  const totalEl = document.getElementById('cart-total');
  if (!container) return;
  if (!cart.length) {
    container.innerHTML = '<p style="text-align:center;color:#888;padding:30px;">السلة فارغة</p>';
    if (totalEl) totalEl.textContent = '0';
    document.getElementById('checkout-form').style.display = 'none';
    return;
  }
  container.innerHTML = cart.map(item => `
    <div class="cart-item">
      <div class="cart-item-info">
        <h4>${item.name}</h4>
        <span>${item.price} ر.س × ${item.qty}</span>
      </div>
      <button class="remove-item" onclick="removeFromCart(${item.id})">×</button>
    </div>
  `).join('');
  const total = cart.reduce((s, i) => s + i.price * i.qty, 0);
  if (totalEl) totalEl.textContent = total.toFixed(0);
  document.getElementById('checkout-form').style.display = 'block';
}

function toggleCart() {
  document.getElementById('cart-sidebar')?.classList.toggle('open');
  document.getElementById('overlay')?.classList.toggle('show');
}

async function checkout() {
  if (!cart.length) return alert('السلة فارغة!');
  const name = document.getElementById('cust-name')?.value.trim() || '';
  const phone = document.getElementById('cust-phone')?.value.trim() || '';
  const total = cart.reduce((s, i) => s + i.price * i.qty, 0);
  const token = localStorage.getItem('user_token') || '';
  try {
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['X-User-Token'] = token;
    const res = await fetch(API + '/api/orders', {
      method: 'POST',
      headers,
      body: JSON.stringify({ items: cart, total, customer_name: name, customer_phone: phone })
    });
    const data = await res.json();
    if (res.ok) {
      alert(data.message || 'تم استلام الطلب!');
      cart = [];
      saveCart();
      renderCart();
      toggleCart();
    } else {
      alert(data.error || 'حدث خطأ');
    }
  } catch (e) {
    alert('خطأ في الاتصال بالسيرفر');
  }
}

// ===== لوحة التحكم =====
function login() {
  const pass = document.getElementById('admin-password').value.trim();
  if (!pass) {
    alert('أدخل كلمة المرور');
    return;
  }
  // نخزن أي كلمة مرور يدخلها المستخدم ونخلي السيرفر يتحقق في كل طلب (X-Admin-Key)
  adminKey = pass;
  localStorage.setItem('admin_key', pass);
  document.getElementById('login-card').style.display = 'none';
  document.getElementById('admin-content').style.display = 'block';
  loadAdminProducts();
  loadOrders();
  loadDiscordStatus();
}

async function loadAdminProducts() {
  const list = document.getElementById('admin-products-list');
  if (!list) return;
  try {
    const res = await fetch(API + '/api/products');
    const products = await res.json();
    if (!products.length) {
      list.innerHTML = '<p class="empty-msg">لا توجد منتجات.</p>';
      return;
    }
    list.innerHTML = products.map(p => `
      <div class="admin-item">
        <div class="admin-item-info">
          <h4>${p.name}</h4>
          <span>${p.price} ر.س</span>
        </div>
        <div class="admin-item-actions">
          <button class="btn-edit" onclick='editProduct(${JSON.stringify(p)})'>تعديل</button>
          <button class="btn-delete" onclick="deleteProduct(${p.id})">حذف</button>
        </div>
      </div>
    `).join('');
  } catch (e) {
    list.innerHTML = '<p class="empty-msg">خطأ في تحميل المنتجات</p>';
  }
}

async function loadOrders() {
  const list = document.getElementById('orders-list');
  if (!list) return;
  try {
    const res = await fetch(API + '/api/orders', {
      headers: { 'X-Admin-Key': adminKey }
    });
    if (!res.ok) {
      list.innerHTML = '<p class="empty-msg">لا يمكن تحميل الطلبات</p>';
      return;
    }
    const orders = await res.json();
    if (!orders.length) {
      list.innerHTML = '<p class="empty-msg">لا توجد طلبات بعد.</p>';
      return;
    }
    list.innerHTML = orders.map(o => {
      const items = JSON.parse(o.items || '[]');
      return `
        <div class="admin-item">
          <div class="admin-item-info">
            <h4>طلب #${o.id} - ${o.customer_name || 'زائر'} ${o.customer_phone || ''}</h4>
            <span>${o.total} ر.س | ${items.map(i => i.name + ' ×' + i.qty).join('، ')}</span>
            <br><small style="color:#888">${o.created_at} | الحالة: ${o.status}</small>
          </div>
        </div>
      `;
    }).join('');
  } catch (e) {
    list.innerHTML = '<p class="empty-msg">خطأ</p>';
  }
}

function editProduct(p) {
  document.getElementById('product-id').value = p.id;
  document.getElementById('product-name').value = p.name;
  document.getElementById('product-price').value = p.price;
  document.getElementById('product-desc').value = p.description || '';
  document.getElementById('product-image').value = p.image || '';
  document.getElementById('form-title').textContent = 'تعديل المنتج';
  document.getElementById('submit-btn').textContent = 'حفظ التعديلات';
  document.getElementById('cancel-btn').style.display = 'inline-block';
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function resetForm() {
  document.getElementById('product-form').reset();
  document.getElementById('product-id').value = '';
  document.getElementById('form-title').textContent = 'إضافة منتج جديد';
  document.getElementById('submit-btn').textContent = 'إضافة المنتج';
  document.getElementById('cancel-btn').style.display = 'none';
}

document.getElementById('product-form')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const id = document.getElementById('product-id').value;
  const body = {
    name: document.getElementById('product-name').value.trim(),
    price: parseFloat(document.getElementById('product-price').value),
    description: document.getElementById('product-desc').value.trim(),
    image: document.getElementById('product-image').value.trim()
  };
  const url = id ? API + '/api/products/' + id : API + '/api/products';
  const method = id ? 'PUT' : 'POST';
  try {
    const res = await fetch(url, {
      method,
      headers: {
        'Content-Type': 'application/json',
        'X-Admin-Key': adminKey
      },
      body: JSON.stringify(body)
    });
    const data = await res.json();
    if (res.ok) {
      alert(data.message || 'تم بنجاح');
      resetForm();
      loadAdminProducts();
    } else {
      alert(data.error || 'خطأ');
    }
  } catch (err) {
    alert('خطأ في الاتصال');
  }
});

async function deleteProduct(id) {
  if (!confirm('هل أنت متأكد من الحذف؟')) return;
  try {
    const res = await fetch(API + '/api/products/' + id, {
      method: 'DELETE',
      headers: { 'X-Admin-Key': adminKey }
    });
    const data = await res.json();
    if (res.ok) {
      alert(data.message);
      loadAdminProducts();
    } else {
      alert(data.error);
    }
  } catch (e) {
    alert('خطأ');
  }
}

// ===== نظام الجزيئات التفاعلية =====
function initParticles() {
  const canvas = document.getElementById('particles-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let width, height;
  let particles = [];
  let mouse = { x: null, y: null };
  const colors = ['#ff6b9d', '#c44dff', '#00d4ff', '#ff9f43', '#10ac84', '#ee5a24', '#5f27cd'];

  function resize() {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
  }
  resize();
  window.addEventListener('resize', resize);

  window.addEventListener('mousemove', (e) => {
    mouse.x = e.clientX;
    mouse.y = e.clientY;
    // أضف جزيئات جديدة عند حركة الماوس
    for (let i = 0; i < 3; i++) {
      particles.push(createParticle(mouse.x, mouse.y));
    }
  });

  function createParticle(x, y) {
    const angle = Math.random() * Math.PI * 2;
    const speed = Math.random() * 2 + 0.5;
    return {
      x: x,
      y: y,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed,
      size: Math.random() * 4 + 1.5,
      color: colors[Math.floor(Math.random() * colors.length)],
      life: 1,
      decay: Math.random() * 0.015 + 0.008
    };
  }

  // جزيئات خلفية ثابتة
  for (let i = 0; i < 60; i++) {
    particles.push({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * 0.4,
      vy: (Math.random() - 0.5) * 0.4,
      size: Math.random() * 2.5 + 0.8,
      color: colors[Math.floor(Math.random() * colors.length)],
      life: 1,
      decay: 0
    });
  }

  function animate() {
    ctx.clearRect(0, 0, width, height);

    // رسم خطوط بين الجزيئات القريبة
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x;
        const dy = particles[i].y - particles[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 120) {
          ctx.beginPath();
          ctx.strokeStyle = particles[i].color;
          ctx.globalAlpha = (1 - dist / 120) * 0.25 * particles[i].life;
          ctx.lineWidth = 0.8;
          ctx.moveTo(particles[i].x, particles[i].y);
          ctx.lineTo(particles[j].x, particles[j].y);
          ctx.stroke();
        }
      }
    }
    ctx.globalAlpha = 1;

    // تحديث ورسم الجزيئات
    for (let i = particles.length - 1; i >= 0; i--) {
      const p = particles[i];
      p.x += p.vx;
      p.y += p.vy;
      p.life -= p.decay;

      // انجذاب خفيف للماوس
      if (mouse.x !== null && p.decay > 0) {
        const dx = mouse.x - p.x;
        const dy = mouse.y - p.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 180) {
          p.vx += dx * 0.0008;
          p.vy += dy * 0.0008;
        }
      }

      // حدود الشاشة للجزيئات الخلفية
      if (p.decay === 0) {
        if (p.x < 0 || p.x > width) p.vx *= -1;
        if (p.y < 0 || p.y > height) p.vy *= -1;
      }

      if (p.life <= 0) {
        particles.splice(i, 1);
        continue;
      }

      ctx.beginPath();
      ctx.arc(p.x, p.y, p.size * p.life, 0, Math.PI * 2);
      ctx.fillStyle = p.color;
      ctx.globalAlpha = p.life * 0.85;
      ctx.fill();

      // توهج
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.size * p.life * 2.5, 0, Math.PI * 2);
      ctx.fillStyle = p.color;
      ctx.globalAlpha = p.life * 0.15;
      ctx.fill();
    }
    ctx.globalAlpha = 1;

    // حافظ على عدد معقول
    if (particles.length > 180) {
      particles.splice(0, particles.length - 180);
    }

    requestAnimationFrame(animate);
  }
  animate();
}

// ===== ديسكورد =====
async function loadDiscordStatus() {
  const notLinked = document.getElementById('discord-not-linked');
  const linked = document.getElementById('discord-linked');
  if (!notLinked || !linked) return;

  try {
    const res = await fetch(API + '/api/discord/me', {
      headers: { 'X-Admin-Key': adminKey }
    });
    const data = await res.json();
    if (data.linked) {
      notLinked.style.display = 'none';
      linked.style.display = 'block';
      document.getElementById('discord-username').textContent = data.username || '—';
      document.getElementById('discord-globalname').textContent = data.global_name ? `الاسم الظاهر: ${data.global_name}` : '';
      document.getElementById('discord-id').textContent = `ID: ${data.id}`;
      if (data.avatar) {
        document.getElementById('discord-avatar').src = data.avatar;
      } else {
        document.getElementById('discord-avatar').src = 'https://cdn.discordapp.com/embed/avatars/0.png';
      }
      document.getElementById('new-username').value = data.username || '';
      document.getElementById('new-globalname').value = data.global_name || '';
    } else {
      notLinked.style.display = 'block';
      linked.style.display = 'none';
    }
  } catch (e) {
    console.error(e);
  }
}

async function updateDiscordProfile() {
  const msg = document.getElementById('discord-msg');
  msg.textContent = 'جاري التحديث على ديسكورد...';
  msg.style.color = '#aaa';

  const payload = {};
  const username = document.getElementById('new-username').value.trim();
  const globalName = document.getElementById('new-globalname').value.trim();
  if (username) payload.username = username;
  // دائماً نرسل global_name حتى لو فاضي (عشان نقدر نمسحه)
  payload.global_name = globalName;

  // استخدم الصورة المقصوصة لو موجودة
  if (typeof cropState !== 'undefined' && cropState.croppedDataUrl) {
    payload.avatar = cropState.croppedDataUrl;
  } else {
    const fileInput = document.getElementById('new-avatar');
    if (fileInput && fileInput.files && fileInput.files[0]) {
      try {
        const base64 = await fileToBase64(fileInput.files[0]);
        payload.avatar = base64;
      } catch (e) {
        msg.textContent = 'خطأ في قراءة الصورة';
        msg.style.color = '#ff6b9d';
        return;
      }
    }
  }

  if (!payload.username && !payload.global_name && !payload.avatar) {
    msg.textContent = 'لم تغير أي شيء!';
    msg.style.color = '#ff6b9d';
    return;
  }

  try {
    const res = await fetch(API + '/api/discord/update', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Admin-Key': adminKey
      },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (res.ok) {
      msg.textContent = data.message || 'تم التحديث بنجاح على حسابك في ديسكورد!';
      msg.style.color = '#10ac84';
      if (typeof cropState !== 'undefined') {
        cropState.croppedDataUrl = null;
        cropState.img = null;
      }
      const previewBox = document.getElementById('avatar-preview-box');
      if (previewBox) previewBox.style.display = 'none';
      loadDiscordStatus();
    } else {
      msg.textContent = data.error || 'فشل التحديث - جرب إعادة ربط الحساب';
      msg.style.color = '#ff6b9d';
      console.error('Discord update error:', data);
    }
  } catch (e) {
    msg.textContent = 'خطأ في الاتصال بالسيرفر';
    msg.style.color = '#ff6b9d';
  }
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

async function unlinkDiscord() {
  if (!confirm('هل أنت متأكد من فك ربط حساب ديسكورد؟')) return;
  try {
    await fetch(API + '/api/discord/unlink', {
      method: 'DELETE',
      headers: { 'X-Admin-Key': adminKey }
    });
    loadDiscordStatus();
  } catch (e) {
    alert('خطأ');
  }
}

// تهيئة
document.addEventListener('DOMContentLoaded', () => {
  loadProducts();
  renderCart();
  updateCartCount();
  initParticles();

  // إذا كان هناك مفتاح أدمن محفوظ، حاول الدخول مباشرة
  if (document.getElementById('admin-content') && adminKey) {
    document.getElementById('login-card').style.display = 'none';
    document.getElementById('admin-content').style.display = 'block';
    loadAdminProducts();
    loadOrders();
    loadDiscordStatus();
  }

  const params = new URLSearchParams(window.location.search);
  if (params.get('discord') === 'success') {
    if (adminKey) {
      document.getElementById('login-card').style.display = 'none';
      document.getElementById('admin-content').style.display = 'block';
      loadDiscordStatus();
      loadAdminProducts();
      loadOrders();
    }
    history.replaceState(null, '', '/admin.html');
  }
  if (params.get('discord') === 'error') {
    const msg = params.get('msg') || 'فشل الربط';
    if (adminKey) {
      document.getElementById('login-card').style.display = 'none';
      document.getElementById('admin-content').style.display = 'block';
      loadDiscordStatus();
    }
    setTimeout(() => {
      alert('فشل ربط ديسكورد:\n' + decodeURIComponent(msg) + '\n\nتأكد أن Client Public مطفي وأن Redirect URI مضبوط بشكل صحيح في Discord Developer Portal.');
    }, 300);
    history.replaceState(null, '', '/admin.html');
  }
});


// ===== محرر الصور الدائري =====
let cropState = {
  img: null,
  scale: 1,
  offsetX: 0,
  offsetY: 0,
  dragging: false,
  lastX: 0,
  lastY: 0,
  croppedDataUrl: null
};

document.getElementById('new-avatar')?.addEventListener('change', function(e) {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = function(ev) {
    const img = new Image();
    img.onload = function() {
      cropState.img = img;
      cropState.scale = 1;
      cropState.offsetX = 0;
      cropState.offsetY = 0;
      cropState.croppedDataUrl = null;
      openCropper();
    };
    img.src = ev.target.result;
  };
  reader.readAsDataURL(file);
});

function openCropper() {
  if (!cropState.img) return;
  const modal = document.getElementById('crop-modal');
  modal.style.display = 'flex';
  document.getElementById('crop-zoom').value = cropState.scale;
  drawCrop();
  setupCropEvents();
}

function closeCropper() {
  document.getElementById('crop-modal').style.display = 'none';
}

function drawCrop() {
  const canvas = document.getElementById('crop-canvas');
  if (!canvas || !cropState.img) return;
  const ctx = canvas.getContext('2d');
  const size = 280;
  ctx.clearRect(0, 0, size, size);

  const img = cropState.img;
  const scale = cropState.scale;
  const iw = img.width * scale;
  const ih = img.height * scale;

  // مركز الصورة مع الإزاحة
  const x = (size - iw) / 2 + cropState.offsetX;
  const y = (size - ih) / 2 + cropState.offsetY;

  ctx.save();
  ctx.beginPath();
  ctx.arc(size/2, size/2, size/2, 0, Math.PI * 2);
  ctx.clip();
  ctx.drawImage(img, x, y, iw, ih);
  ctx.restore();

  // حدود الدائرة
  ctx.beginPath();
  ctx.arc(size/2, size/2, size/2 - 1, 0, Math.PI * 2);
  ctx.strokeStyle = '#5865F2';
  ctx.lineWidth = 2;
  ctx.stroke();
}

function setupCropEvents() {
  const canvas = document.getElementById('crop-canvas');
  const zoom = document.getElementById('crop-zoom');
  if (!canvas) return;

  zoom.oninput = function() {
    cropState.scale = parseFloat(this.value);
    drawCrop();
  };

  canvas.onmousedown = function(e) {
    cropState.dragging = true;
    cropState.lastX = e.clientX;
    cropState.lastY = e.clientY;
  };
  window.onmouseup = function() { cropState.dragging = false; };
  window.onmousemove = function(e) {
    if (!cropState.dragging) return;
    cropState.offsetX += e.clientX - cropState.lastX;
    cropState.offsetY += e.clientY - cropState.lastY;
    cropState.lastX = e.clientX;
    cropState.lastY = e.clientY;
    drawCrop();
  };

  // لمس للموبايل
  canvas.ontouchstart = function(e) {
    cropState.dragging = true;
    cropState.lastX = e.touches[0].clientX;
    cropState.lastY = e.touches[0].clientY;
  };
  window.ontouchend = function() { cropState.dragging = false; };
  window.ontouchmove = function(e) {
    if (!cropState.dragging) return;
    cropState.offsetX += e.touches[0].clientX - cropState.lastX;
    cropState.offsetY += e.touches[0].clientY - cropState.lastY;
    cropState.lastX = e.touches[0].clientX;
    cropState.lastY = e.touches[0].clientY;
    drawCrop();
  };
}

function applyCrop() {
  const canvas = document.getElementById('crop-canvas');
  // نصدر صورة دائرية بحجم مناسب لديسكورد (128x128 أو 256x256)
  const out = document.createElement('canvas');
  out.width = 256;
  out.height = 256;
  const ctx = out.getContext('2d');
  ctx.beginPath();
  ctx.arc(128, 128, 128, 0, Math.PI * 2);
  ctx.clip();

  const img = cropState.img;
  const scale = cropState.scale * (256 / 280);
  const iw = img.width * scale;
  const ih = img.height * scale;
  const x = (256 - iw) / 2 + cropState.offsetX * (256 / 280);
  const y = (256 - ih) / 2 + cropState.offsetY * (256 / 280);
  ctx.drawImage(img, x, y, iw, ih);

  cropState.croppedDataUrl = out.toDataURL('image/png');
  document.getElementById('avatar-preview-img').src = cropState.croppedDataUrl;
  document.getElementById('avatar-preview-box').style.display = 'block';
  closeCropper();
}

function clearAvatar() {
  cropState.img = null;
  cropState.croppedDataUrl = null;
  document.getElementById('new-avatar').value = '';
  document.getElementById('avatar-preview-box').style.display = 'none';
}

