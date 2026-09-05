// 极简 HTTP 封装（@ohos.net.http），返回响应体字符串，非 200 抛错（带后端中文错误信息）
import { http } from '@kit.NetworkKit';
import { BASE_URL } from '../common/Constants';

interface HttpHeader {
  'Content-Type': string;
}

const JSON_HEADER: HttpHeader = { 'Content-Type': 'application/json' };

// 后端错误响应体（FastAPI detail / 契约 message）
interface ErrorBody {
  detail: string;
  message: string;
}

function extractError(res: http.HttpResponse): string {
  let msg = `HTTP ${res.responseCode}`;
  try {
    const text = res.result as string;
    const body = JSON.parse(text) as ErrorBody;
    if (body.detail !== undefined && body.detail !== '') {
      msg = body.detail;
    } else if (body.message !== undefined && body.message !== '') {
      msg = body.message;
    }
  } catch (e) {
    // 解析失败，用默认 msg
  }
  return msg;
}

export async function getText(path: string): Promise<string> {
  const req = http.createHttp();
  try {
    const res = await req.request(BASE_URL + path, {
      method: http.RequestMethod.GET,
      expectDataType: http.HttpDataType.STRING,
      connectTimeout: 10000,
      readTimeout: 10000
    });
    if (res.responseCode !== http.ResponseCode.OK && res.responseCode !== http.ResponseCode.CREATED) {
      throw new Error(extractError(res));
    }
    return res.result as string;
  } finally {
    req.destroy();
  }
}

export async function postText(path: string, body: string): Promise<string> {
  const req = http.createHttp();
  try {
    const res = await req.request(BASE_URL + path, {
      method: http.RequestMethod.POST,
      header: JSON_HEADER,
      extraData: body,
      expectDataType: http.HttpDataType.STRING,
      connectTimeout: 10000,
      readTimeout: 180000
    });
    if (res.responseCode !== http.ResponseCode.OK && res.responseCode !== http.ResponseCode.CREATED) {
      throw new Error(extractError(res));
    }
    return res.result as string;
  } finally {
    req.destroy();
  }
}
