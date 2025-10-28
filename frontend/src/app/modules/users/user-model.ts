export interface UserI {
  id?: number;
  username: string;
  password?: string;
  first_name: string;
  last_name: string;
  email: string;
  avatar?: string; // URL o base64
  role?: {
    id: number;
    name: string;
  };
}
