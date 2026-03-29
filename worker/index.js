/**
 * K-pop Tracker — Discord Interaction Handler (Cloudflare Worker)
 *
 * 「詳しく」ボタンがクリックされたら、詳細情報をエフェメラルメッセージで返す。
 * custom_id: "kpop_detail_{group_id}_{index}"
 * 環境変数: DISCORD_PUBLIC_KEY, GITHUB_REPO
 */

const INTERACTION_PING = 1;
const INTERACTION_COMPONENT = 3;
const RESPONSE_PONG = 1;
const RESPONSE_MESSAGE = 4;
const FLAG_EPHEMERAL = 64;

// グループ別カラー
const GROUP_COLORS = {
  ive: 0x9b59b6,
  le_sserafim: 0xe74c3c,
  twice: 0xf39c12,
  newjeans: 0x3498db,
  h2h: 0x2ecc71,
};

const GROUP_EMOJI = {
  ive: "💜",
  le_sserafim: "🔴",
  twice: "🟠",
  newjeans: "🔵",
  h2h: "💚",
};

export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return new Response("Method Not Allowed", { status: 405 });
    }

    const { isValid, body } = await verifyRequest(request, env.DISCORD_PUBLIC_KEY);
    if (!isValid) {
      return new Response("Invalid signature", { status: 401 });
    }

    const interaction = JSON.parse(body);

    if (interaction.type === INTERACTION_PING) {
      return jsonResponse({ type: RESPONSE_PONG });
    }

    if (interaction.type === INTERACTION_COMPONENT) {
      const customId = interaction.data.custom_id;

      if (customId.startsWith("kpop_detail_")) {
        const parts = customId.split("_");
        // "kpop_detail_{group_id}_{index}"
        const groupId = parts[2];
        const index = parseInt(parts[3], 10);
        return await handleDetailButton(groupId, index, env);
      }
    }

    return new Response("Unknown interaction", { status: 400 });
  },
};

async function handleDetailButton(groupId, index, env) {
  try {
    const rawUrl = `https://raw.githubusercontent.com/${env.GITHUB_REPO}/master/data/latest.json`;
    const resp = await fetch(rawUrl, {
      headers: { "User-Agent": "KpopTracker-Worker/1.0" },
      cf: { cacheTtl: 300 },
    });

    if (!resp.ok) {
      return ephemeral("詳細データの取得に失敗しました。");
    }

    const data = await resp.json();
    const item = data.items?.[index];

    if (!item) {
      return ephemeral("この記事の詳細情報が見つかりませんでした。");
    }

    const color = GROUP_COLORS[item.group_id] || 0xff69b4;
    const emoji = GROUP_EMOJI[item.group_id] || "🎵";
    const catLabel =
      item.category === "ticket"
        ? "🔥🎫 チケット"
        : item.category === "tv"
          ? "📺 TV出演"
          : item.category === "comeback"
            ? "🎶 カムバック"
            : "📌 イベント";

    return jsonResponse({
      type: RESPONSE_MESSAGE,
      data: {
        embeds: [
          {
            title: `${emoji} ${item.headline}`,
            description: item.detail,
            color: color,
            fields: [
              {
                name: "カテゴリ",
                value: catLabel,
                inline: true,
              },
              {
                name: "出典",
                value: item.url
                  ? `[${item.source || "リンク"}](${item.url})`
                  : item.source || "不明",
                inline: true,
              },
            ],
            footer: { text: "🎵 K-pop Tracker" },
          },
        ],
        flags: FLAG_EPHEMERAL,
      },
    });
  } catch (e) {
    return ephemeral(`エラーが発生しました: ${e.message}`);
  }
}

function ephemeral(text) {
  return jsonResponse({
    type: RESPONSE_MESSAGE,
    data: { content: text, flags: FLAG_EPHEMERAL },
  });
}

function jsonResponse(data) {
  return new Response(JSON.stringify(data), {
    headers: { "Content-Type": "application/json" },
  });
}

// ── Ed25519 署名検証 ────────────────────────────────────────────────────────
async function verifyRequest(request, publicKey) {
  const signature = request.headers.get("x-signature-ed25519");
  const timestamp = request.headers.get("x-signature-timestamp");
  const body = await request.text();

  if (!signature || !timestamp) {
    return { isValid: false, body };
  }

  try {
    const key = await crypto.subtle.importKey(
      "raw",
      hexToUint8Array(publicKey),
      { name: "NODE-ED25519", namedCurve: "NODE-ED25519" },
      true,
      ["verify"]
    );

    const isValid = await crypto.subtle.verify(
      "NODE-ED25519",
      key,
      hexToUint8Array(signature),
      new TextEncoder().encode(timestamp + body)
    );

    return { isValid, body };
  } catch {
    return { isValid: false, body };
  }
}

function hexToUint8Array(hex) {
  return new Uint8Array(hex.match(/.{1,2}/g).map((b) => parseInt(b, 16)));
}
