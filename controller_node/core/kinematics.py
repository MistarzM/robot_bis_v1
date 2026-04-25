import math
import numpy as np
from core import config

class RobotKinematics:
    def __init__(self):
        self.pos = config.HOME_POS.copy()
        
        self.last_t4 = self.raw_to_rad(config.HOME_POS[4], 4)
        self.last_t5 = self.raw_to_rad(config.HOME_POS[5], 5)
        self.last_t6 = self.raw_to_rad(config.HOME_POS[6], 6)

    def raw_to_rad(self, raw_val, servo_id):
        return math.radians((raw_val - config.ZERO_POS[servo_id]) * 0.088)

    def rad_to_raw(self, rad, servo_id):
        raw = int(config.ZERO_POS[servo_id] + (math.degrees(rad) / 0.088))
        return np.clip(raw, 0, 4095)

    def dh_matrix(self, a, alpha, d, theta):
        ct, st = math.cos(theta), math.sin(theta)
        ca, sa = math.cos(alpha), math.sin(alpha)
        return [
            [ct, -st*ca,  st*sa, a*ct],
            [st,  ct*ca, -ct*sa, a*st],
            [0,   sa,     ca,    d],
            [0,   0,      0,     1]
        ]

    def mult_matrix(self, m1, m2):
        res = [[0]*4 for _ in range(4)]
        for i in range(4):
            for j in range(4):
                res[i][j] = (m1[i][0]*m2[0][j] + m1[i][1]*m2[1][j] + 
                             m1[i][2]*m2[2][j] + m1[i][3]*m2[3][j])
        return res

    def get_kinematics(self, pos_dict):
        t1 = self.raw_to_rad(pos_dict[0], 0)
        t2 = self.raw_to_rad(pos_dict[1], 1)
        t3 = self.raw_to_rad(pos_dict[3], 3)
        t4 = self.raw_to_rad(pos_dict[4], 4)
        t5 = self.raw_to_rad(pos_dict[5], 5)
        t6 = self.raw_to_rad(pos_dict[6], 6)

        T1 = self.dh_matrix(config.A2, math.pi/2, config.A1, t1)
        T2 = self.dh_matrix(config.A3, 0, 0, t2)
        T3 = self.dh_matrix(config.A4, math.pi/2, 0, t3)
        T4 = self.dh_matrix(0, -math.pi/2, config.A5, t4)
        T5 = self.dh_matrix(0, math.pi/2, 0, t5)
        T6 = self.dh_matrix(0, 0, config.A6, t6)

        T01 = T1
        T02 = self.mult_matrix(T01, T2)
        T03 = self.mult_matrix(T02, T3)
        T04 = self.mult_matrix(T03, T4)
        T05 = self.mult_matrix(T04, T5)
        T06 = self.mult_matrix(T05, T6)

        shoulder = [round(T01[0][3], 1), round(T01[1][3], 1), round(T01[2][3], 1)]
        elbow    = [round(T02[0][3], 1), round(T02[1][3], 1), round(T02[2][3], 1)]
        wrist    = [round(T04[0][3], 1), round(T04[1][3], 1), round(T04[2][3], 1)]
        ee_pos   = [round(T06[0][3], 1), round(T06[1][3], 1), round(T06[2][3], 1)]

        cb = np.clip(T06[2][2], -1.0, 1.0)
        pitch = math.acos(cb)
        
        if abs(math.sin(pitch)) > 0.001:
            yaw = math.atan2(T06[1][2], T06[0][2])
            roll = math.atan2(T06[2][1], -T06[2][0])
        else:
            yaw = math.atan2(T06[1][0], T06[0][0])
            roll = 0.0
        
        ee_full_pose = [ee_pos[0], ee_pos[1], ee_pos[2], yaw, pitch, roll]
        return [shoulder, elbow, wrist, ee_pos], ee_full_pose

    def solve_ik(self, target_pose):
        yaw, pitch, roll = target_pose[3], target_pose[4], target_pose[5]
        
        cy, sy = math.cos(yaw), math.sin(yaw)
        cp, sp = math.cos(pitch), math.sin(pitch)
        cr, sr = math.cos(roll), math.sin(roll)

        R06 = np.array([
            [cy*cp*cr - sy*sr, -cy*cp*sr - sy*cr, cy*sp],
            [sy*cp*cr + cy*sr, -sy*cp*sr + cy*cr, sy*sp],
            [-sp*cr,            sp*sr,            cp]
        ])

        EE_pos = np.array([target_pose[0], target_pose[1], target_pose[2]])
        Z6_axis = R06[:, 2] 
        WC = EE_pos - Z6_axis * config.A6

        t1 = math.atan2(WC[1], WC[0])

        r_plan = math.sqrt(WC[0]**2 + WC[1]**2) - config.A2 
        z_plan = WC[2] - config.A1 
        
        L = math.sqrt(r_plan**2 + z_plan**2) 
        L1 = config.A3 
        L2 = math.sqrt(config.A4**2 + config.A5**2) 
        
        if L > L1 + L2: 
            L = L1 + L2 - 0.001 
            
        cos_q3 = (L**2 - L1**2 - L2**2) / (2 * L1 * L2)
        cos_q3 = np.clip(cos_q3, -1.0, 1.0)
        q3_inner = math.acos(cos_q3)
        
        gamma = math.atan2(config.A4, config.A5) 
        t3 = math.pi/2 - q3_inner - gamma 

        cos_q2 = (L**2 + L1**2 - L2**2) / (2 * L * L1)
        cos_q2 = np.clip(cos_q2, -1.0, 1.0)
        q2_inner = math.acos(cos_q2)
        
        alpha = math.atan2(z_plan, r_plan)
        t2 = alpha + q2_inner 

        T1_mat = self.dh_matrix(config.A2, math.pi/2, config.A1, t1)
        T2_mat = self.dh_matrix(config.A3, 0, 0, t2)
        T3_mat = self.dh_matrix(config.A4, math.pi/2, 0, t3)
        
        T03 = self.mult_matrix(T1_mat, self.mult_matrix(T2_mat, T3_mat))
        R03 = np.array([
            [T03[0][0], T03[0][1], T03[0][2]],
            [T03[1][0], T03[1][1], T03[1][2]],
            [T03[2][0], T03[2][1], T03[2][2]]
        ])
        
        R36 = np.dot(R03.T, R06)
        
        r_val = math.sqrt(R36[0,2]**2 + R36[1,2]**2)
        
        if r_val > 0.02:
            t5_A = math.atan2(r_val, R36[2,2])
            t4_A = math.atan2(R36[1,2], R36[0,2])
            t6_A = math.atan2(R36[2,1], -R36[2,0])
            
            t5_B = math.atan2(-r_val, R36[2,2])
            t4_B = math.atan2(-R36[1,2], -R36[0,2])
            t6_B = math.atan2(-R36[2,1], R36[2,0])
            
            def ang_diff(a, b):
                return abs((a - b + math.pi) % (2*math.pi) - math.pi)
            
            cost_A = ang_diff(t4_A, self.last_t4) + ang_diff(t5_A, self.last_t5) + ang_diff(t6_A, self.last_t6)
            cost_B = ang_diff(t4_B, self.last_t4) + ang_diff(t5_B, self.last_t5) + ang_diff(t6_B, self.last_t6)
            
            if cost_A <= cost_B:
                t4, t5, t6 = t4_A, t5_A, t6_A
            else:
                t4, t5, t6 = t4_B, t5_B, t6_B
        else:
            t4 = self.last_t4
            sign = 1.0 if self.last_t5 >= 0 else -1.0
            t5 = math.atan2(r_val * sign, R36[2,2])
            if R36[2,2] > 0:
                t6 = math.atan2(-R36[0,1], R36[0,0]) - t4
            else:
                t6 = math.atan2(R36[0,1], -R36[0,0]) + t4

        self.last_t4, self.last_t5, self.last_t6 = t4, t5, t6

        target_raw = {
            0: self.rad_to_raw(t1, 0), 1: self.rad_to_raw(t2, 1),
            3: self.rad_to_raw(t3, 3), 4: self.rad_to_raw(t4, 4),
            5: self.rad_to_raw(t5, 5), 6: self.rad_to_raw(t6, 6)
        }
        
        for servo_id in [0, 1, 3, 4, 5, 6]:
            diff = target_raw[servo_id] - self.pos[servo_id]
            step = np.clip(diff, -config.MAX_STEP, config.MAX_STEP)
            self.pos[servo_id] += step