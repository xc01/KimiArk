from run_medical_groups import *

def main():
    base=middle_robot_base()+[change(ANSEL,'DEPLOY',1321,tile=[5,5],direction='RIGHT'),change(STEWARD,'DEPLOY',6381,tile=[5,3],direction='RIGHT')]
    for tile,d in [([5,6],'DOWN'),([5,6],'LEFT'),([2,7],'UP'),([2,5],'UP')]:
        r=variant('JOINT_HIBI'+str(tile[0])+str(tile[1])+d,base+[change(HIBISC,'DEPLOY',1681,tile=tile,direction=d)],'Ansel relocation kept Melantha but Hibiscus died@3311. Relocate Hibiscus coverage/lock exposure as a group to preserve both real medics and sustain cannon output; actual heals and splash recipients decide.')
        if r.get('observed',{}).get('complete_win'):return
    # Preserve lower-robot branch without long-lived Melantha by explicitly replacing lower outer duty after a legal cooldown; later healer bias checks only if new observations support.

if __name__=='__main__':main()
